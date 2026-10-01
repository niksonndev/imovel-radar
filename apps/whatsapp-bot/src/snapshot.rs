//! Snapshot consistente do arquivo SQLite que guarda a sessão do WhatsApp.
//!
//! O store do `whatsapp-rust` roda em **WAL**: enquanto o cliente está
//! conectado, o pool mantém o arquivo aberto e boa parte do estado recente vive
//! no `-wal`/`-shm` ao lado do `.db`. Copiar o `.db` com `fs::read` (como era
//! feito) entrega um snapshot sem as páginas ainda não checkpointadas — na
//! prática, um banco que pode nem ter as tabelas visíveis. Restaurado depois de
//! um deploy, ele falha ao abrir e o bot cai no pareamento por QR: exatamente o
//! caminho que aumenta o risco de ban.
//!
//! `VACUUM INTO` usa o caminho de leitura consistente do próprio SQLite (enxerga
//! o WAL) e devolve um banco autônomo, pronto para ir ao Neon e ser escrito de
//! volta num boot limpo.

use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};

use diesel::connection::SimpleConnection;
use diesel::prelude::*;

/// Lê um snapshot consistente de `src` (`VACUUM INTO`) e devolve os bytes.
///
/// `dst` é um temporário ao lado do arquivo de sessão; é sempre removido, mesmo
/// quando o snapshot falha no meio.
pub fn snapshot_sqlite(src: &str, dst: &str) -> anyhow::Result<Vec<u8>> {
    let dst_path = Path::new(dst);
    if dst_path.exists() {
        std::fs::remove_file(dst_path)?;
    }
    let mut conn = SqliteConnection::establish(src)
        .map_err(|error| anyhow::anyhow!("abrir sqlite de origem ({src}): {error}"))?;
    // `VACUUM INTO` não aceita placeholder para o destino: vai no literal, com as
    // aspas simples escapadas. O caminho é nosso (deriva de WHATSAPP_SESSION_PATH).
    let escaped = dst.replace('\'', "''");
    let result = conn
        .batch_execute(&format!("VACUUM INTO '{escaped}';"))
        .map_err(|error| anyhow::anyhow!("VACUUM INTO {dst}: {error}"));
    drop(conn);
    if let Err(error) = result {
        let _ = std::fs::remove_file(dst_path);
        return Err(error);
    }
    let bytes = std::fs::read(dst_path)?;
    let _ = std::fs::remove_file(dst_path);
    Ok(bytes)
}

/// Contador monotônico para o sufixo do snapshot temporário.
static SNAPSHOT_NONCE: AtomicU64 = AtomicU64::new(0);

/// Caminho do temporário usado por [`snapshot_sqlite`].
///
/// O nome é único por chamada (pid + contador): o backup periódico (5 min) e o
/// snapshot final do shutdown podem rodar juntos e não podem disputar o mesmo
/// arquivo temporário — `VACUUM INTO` falha quando o destino já existe.
pub fn snapshot_path(session_path: &str) -> String {
    let nonce = SNAPSHOT_NONCE.fetch_add(1, Ordering::Relaxed);
    format!("{session_path}.{}.{}.snapshot", std::process::id(), nonce)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(diesel::QueryableByName)]
    struct Row {
        #[diesel(sql_type = diesel::sql_types::BigInt)]
        n: i64,
    }

    fn scratch_dir(tag: &str) -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "wa-snapshot-{tag}-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&dir).expect("criar diretório de teste");
        dir
    }

    /// O caso que motivou o `VACUUM INTO`: um banco em WAL com dados ainda só no
    /// `-wal` (nada checkpointado) precisa sair inteiro no snapshot. Um
    /// `fs::read` do `.db` falharia aqui — é o teste de regressão.
    #[test]
    fn snapshot_inclui_as_paginas_ainda_no_wal() {
        let dir = scratch_dir("wal");
        let src = dir.join("session.db");
        let src = src.display().to_string();

        let mut conn = SqliteConnection::establish(&src).expect("abrir origem");
        conn.batch_execute("PRAGMA journal_mode=WAL;").unwrap();
        conn.batch_execute("CREATE TABLE t (v TEXT NOT NULL);")
            .unwrap();
        conn.batch_execute("INSERT INTO t (v) VALUES ('credencial');")
            .unwrap();

        // Prova o cenário: o arquivo principal, sozinho, ainda não tem a tabela.
        let raw = std::fs::read(&src).unwrap();
        let probe = dir.join("probe.db");
        std::fs::write(&probe, &raw).unwrap();
        let mut probe_conn = SqliteConnection::establish(&probe.display().to_string()).unwrap();
        assert!(
            probe_conn.batch_execute("SELECT count(*) FROM t;").is_err(),
            "sem checkpoint, o .db cru não deveria ter a tabela — é o bug do fs::read"
        );

        // Com a conexão de escrita ABERTA (WAL vivo), o snapshot tem de vir completo.
        let snapshot = snapshot_sqlite(&src, &dir.join("snap.db").display().to_string()).unwrap();
        drop(conn);

        let restored_path = dir.join("restored.db");
        std::fs::write(&restored_path, &snapshot).unwrap();
        let mut restored =
            SqliteConnection::establish(&restored_path.display().to_string()).unwrap();
        let row = diesel::sql_query("SELECT count(*) AS n FROM t")
            .get_result::<Row>(&mut restored)
            .expect("tabela e linha sobrevivem ao snapshot");
        assert_eq!(row.n, 1);

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn snapshot_path_fica_ao_lado_da_sessao_e_e_unico_por_chamada() {
        let first = snapshot_path("/data/whatsapp.db");
        let second = snapshot_path("/data/whatsapp.db");
        assert!(first.starts_with("/data/whatsapp.db."));
        assert!(first.ends_with(".snapshot"));
        assert_ne!(first, second, "cada chamada precisa de um temporário próprio");
    }
}
