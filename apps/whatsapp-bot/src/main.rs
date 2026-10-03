use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use chrono::Utc;
use whatsapp_bot::ai::transcribe_audio;
use whatsapp_bot::config::{ensure_parent_dir, Config};
use whatsapp_bot::db::{Db, SessionLock};
use whatsapp_bot::handlers::{handle_text, handle_transcribed_audio, should_show_typing};
use whatsapp_bot::http;
use whatsapp_bot::jobs::{due, now_maceio, read_stamp, run_daily, write_stamp, Sender};
use whatsapp_bot::ops;
use whatsapp_bot::snapshot::{snapshot_path, snapshot_sqlite};
use whatsapp_bot::wa::{button_reply, qr_ascii, shape, Pairing, WaSender};
use whatsapp_rust::bot::{Bot, EventDelivery};
use whatsapp_rust::prelude::*;
use whatsapp_rust::store::SqliteStore;
use whatsapp_rust::wacore_binary::JidExt;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cfg = Arc::new(Config::from_env()?);
    tracing_subscriber::fmt()
        .with_env_filter(cfg.log_filter())
        .init();
    ensure_parent_dir(&cfg.session_path)?;
    ensure_parent_dir(&cfg.notify_stamp_path)?;

    let db = Db::connect(&cfg.database_url).await?;
    let http_client = reqwest::Client::builder()
        .timeout(Duration::from_secs(20))
        .build()?;
    let pairing = Arc::new(Pairing::default());

    let port = cfg.port;
    let secret = cfg.pair_secret.clone();
    let pairing_http = pairing.clone();
    let http_task = tokio::spawn(async move {
        if let Err(error) = http::serve(port, pairing_http, secret).await {
            tracing::error!(%error, "http encerrou");
        }
    });

    // Gambiarra keep-alive: Render free dorme sem tráfego HTTP de entrada. O bot
    // se auto-pinga (a própria URL pública + /health) a cada 10 min para ficar vivo.
    let ping_cfg = cfg.clone();
    let ping_http = http_client.clone();
    let ping_task = tokio::spawn(async move {
        let base = ping_cfg
            .render_external_url
            .trim_end_matches('/')
            .to_string();
        if base.is_empty() {
            return;
        }
        let url = format!("{base}/health");
        tracing::info!(%url, "auto-ping ativo (10 min)");
        loop {
            tokio::time::sleep(Duration::from_secs(600)).await;
            match ping_http.get(&url).send().await {
                Ok(resp) => tracing::info!(status = resp.status().as_u16(), "auto-ping render"),
                Err(error) => tracing::warn!(%error, "auto-ping render falhou"),
            }
        }
    });

    // Serializa a sessão: só uma instância fala com o WhatsApp por vez. Num
    // deploy o Render pode sobrepor instâncias por alguns segundos e duas
    // conexões com a MESMA identidade fazem o WhatsApp derrubar uma delas — e o
    // processo derrubado gravaria um snapshot "deslogado" por cima do bom.
    // O lock é consultivo (Postgres), cai sozinho se o processo morrer.
    let session_lock = acquire_session_lock(&db, &cfg).await;

    // Anti-repair: se o arquivo local de sessão não existe, restaura do Neon
    // (evita re-emparelhar por QR após reinício do Render free). O snapshot é
    // consistente (VACUUM INTO): traz o estado real do SQLite que roda em WAL,
    // inclusive as páginas que ainda não foram checkpointadas.
    let session_file = std::path::Path::new(&cfg.session_path);
    let missing = !session_file.exists()
        || std::fs::metadata(session_file)
            .map(|m| m.len() == 0)
            .unwrap_or(true);
    let mut restored_from_backup = false;
    if missing {
        match db.load_session_backup().await {
            Ok(Some(backup)) if !backup.payload.is_empty() => {
                match std::fs::write(&cfg.session_path, &backup.payload) {
                    Ok(()) => {
                        restored_from_backup = true;
                        if backup.logged_in {
                            tracing::info!("sessão do WhatsApp restaurada do Neon (logada)");
                        } else {
                            tracing::warn!(
                                "sessão restaurada do Neon foi tirada DESLOGADA; \
                                 pode ser preciso re-parear"
                            );
                        }
                    }
                    Err(error) => tracing::error!(%error, "restaurar sessão do Neon"),
                }
            }
            Ok(_) => {}
            Err(error) => tracing::error!(%error, "ler backup da sessão no Neon"),
        }
    }

    // Ciclo de pareamento: o cliente do whatsapp-rust se desconecta sozinho
    // quando os QRs se esgotam sem pareamento (~160 s) e um cliente encerrado
    // não pode ser reiniciado — cada ciclo precisa de um cliente novo para
    // voltar a oferecer QR. Depois de pareado o ciclo termina e o bot segue com
    // o keepalive/reconexão próprios da lib.
    // Um snapshot foi restaurado mas o cliente está pedindo QR de novo: é o
    // cenário de re-pareamento. Avisa uma vez nos logs.
    let re_pair_alerted = Arc::new(AtomicBool::new(false));
    let (client, handle) = 'pareamento: loop {
        let backend = SqliteStore::new(&cfg.session_path).await?;
        let pairing_qr = pairing.clone();
        let pairing_events = pairing.clone();
        let message_db = db.clone();
        let message_cfg = cfg.clone();
        let message_http = http_client.clone();

        let bot = Bot::builder()
        .with_backend(backend)
        .skip_history_sync()
        .with_event_delivery(EventDelivery::Ordered { capacity: 256 })
        .on_qr_code({
            let alerted = re_pair_alerted.clone();
            move |code, timeout| {
                let pairing = pairing_qr.clone();
                let alerted = alerted.clone();
                async move {
                    let text = code.to_string();
                    match qr_ascii(&text) {
                        Ok(ascii) => println!("{ascii}"),
                        Err(_) => println!("QR recebido. Abra /pair para a imagem."),
                    }
                    if restored_from_backup && !alerted.swap(true, Ordering::SeqCst) {
                        ops::alert(
                            "⚠️ André (WhatsApp): a sessão restaurada não entrou e o assistente \
                             está oferecendo QR de re-pareamento.",
                        )
                        .await;
                    }
                    pairing.set_qr(text, timeout);
                }
            }
        })
        .on_event({
            let alerted = re_pair_alerted.clone();
            move |event, _client| {
                let pairing = pairing_events.clone();
                let alerted = alerted.clone();
                async move {
                    match &*event {
                        Event::Connected(_) => {
                            pairing.mark_connected();
                            tracing::info!("conectado ao WhatsApp");
                        }
                        Event::PairingQrCodesExhausted(_) => {
                            // Sem pareamento os QRs se esgotam e o cliente se
                            // desconecta; o supervisor abaixo sobe um cliente novo.
                            pairing.mark_exhausted();
                            tracing::warn!("QRs esgotados sem pareamento");
                            if restored_from_backup && !alerted.swap(true, Ordering::SeqCst) {
                                ops::alert(
                                    "⚠️ André (WhatsApp): QRs de re-pareamento esgotados \
                                     sem ninguém escanear.",
                                )
                                .await;
                            }
                        }
                        _ => {}
                    }
                }
            }
        })
        .on_message(move |ctx| {
            let db = message_db.clone();
            let cfg = message_cfg.clone();
            let http_client = message_http.clone();
            async move {
                if ctx.info.source.is_from_me
                    || ctx.info.source.chat.is_group()
                    || ctx.info.source.chat.is_broadcast_list()
                    || ctx.info.source.chat.is_status_broadcast()
                {
                    return;
                }
                let chat = ctx.info.source.chat.clone();
                let jid = chat.to_string();
                let audio = ctx.message.get_base_message().audio_message.as_option();
                // Um toque em botão chega como resposta interativa, nunca como
                // texto. O id do botão é a própria opção numerada ("1", "2"),
                // então ele entra no roteador como se tivesse sido digitado.
                let texto = ctx.message.text_content().map(str::to_string);
                let toque = button_reply(&ctx.message);
                // Só metadados: distingue "não chegou" de "não entendeu" sem
                // registrar conteúdo.
                tracing::info!(
                    texto = texto.is_some(),
                    audio = audio.is_some(),
                    botao = toque.is_some(),
                    "mensagem recebida"
                );
                let body = texto.or(toque);
                if body.is_none() && audio.is_none() {
                    // Um toque que não soubemos ler cai aqui: sem este log ele é
                    // descartado em silêncio e o sintoma é "o botão não funciona".
                    tracing::warn!(
                        campos = %shape(&ctx.message),
                        "mensagem sem texto, áudio ou botão reconhecido"
                    );
                    return;
                }
                let chat_id = match db.ensure_whatsapp_user(&jid).await {
                    Ok(chat_id) => chat_id,
                    Err(error) => {
                        tracing::error!(%error, "ensure user");
                        let _ = ctx.reply("Não consegui acessar o radar agora.").await;
                        return;
                    }
                };
                let result = if let Some(body) = body {
                    if should_show_typing(&body) {
                        let _ = ctx.client.chatstate().send_composing(&chat).await;
                    }
                    handle_text(&db, &cfg, &http_client, chat_id, &body).await
                } else if let Some(audio) = audio {
                    if cfg.llm_provider != "openai" || cfg.openai_api_key.is_empty() {
                        let _ = ctx.reply("A transcrição de áudio não está habilitada agora. Envie sua solicitação por texto.").await;
                        return;
                    }
                    if audio.view_once.unwrap_or(false) {
                        let _ = ctx.reply("Não transcrevo áudios de visualização única. Envie texto ou um áudio normal.").await;
                        return;
                    }
                    let duration = audio.seconds.unwrap_or(0);
                    if duration > cfg.assistant_max_audio_seconds {
                        let _ = ctx.reply(format!("O áudio pode ter no máximo {} segundos. Envie um trecho menor.", cfg.assistant_max_audio_seconds)).await;
                        return;
                    }
                    if audio.file_length.unwrap_or(0) > cfg.assistant_max_audio_bytes as u64 {
                        let _ = ctx.reply("O arquivo de áudio é grande demais. Envie um áudio menor.").await;
                        return;
                    }
                    match db.consume_assistant_usage(chat_id, Some(duration), &cfg).await {
                        Ok(true) => {}
                        Ok(false) => {
                            let user = db.get_user(chat_id).await.ok().flatten();
                            let pro = Db::is_pro(user.as_ref(), Utc::now());
                            let limit = if pro { cfg.assistant_pro_audio_per_day } else { cfg.assistant_free_audio_per_day };
                            let _ = ctx.reply(format!("Você atingiu o limite diário de {limit} áudios do {}. Tente novamente amanhã.", if pro { "Radar Pro" } else { "plano grátis" })).await;
                            return;
                        }
                        Err(error) => {
                            tracing::error!(%error, "reservar quota para áudio");
                            let _ = ctx.reply("Não consegui validar seu limite de áudio agora. Tente novamente.").await;
                            return;
                        }
                    }
                    let _ = ctx.client.chatstate().send_composing(&chat).await;
                    let bytes = match ctx.client.download(audio).await {
                        Ok(bytes) if bytes.len() <= cfg.assistant_max_audio_bytes => bytes,
                        Ok(_) => {
                            let _ = ctx.reply("O arquivo de áudio é grande demais. Envie um áudio menor.").await;
                            return;
                        }
                        Err(error) => {
                            tracing::warn!(%error, "download de áudio falhou");
                            let _ = ctx.reply("Não consegui baixar seu áudio agora. Tente novamente ou envie por texto.").await;
                            return;
                        }
                    };
                    let mime = audio
                        .mimetype
                        .as_deref()
                        .unwrap_or("audio/ogg")
                        .split(';')
                        .next()
                        .unwrap_or("audio/ogg")
                        .trim()
                        .to_lowercase();
                    match transcribe_audio(&http_client, &cfg, bytes, &mime).await {
                        Ok(Some(text)) => handle_transcribed_audio(
                            &db, &cfg, &http_client, chat_id, &text, duration,
                        )
                        .await,
                        Ok(None) => {
                            let _ = ctx.reply("Não consegui transcrever esse áudio. Tente novamente ou envie por texto.").await;
                            return;
                        }
                        Err(error) => {
                            tracing::warn!(%error, "transcrição WhatsApp falhou");
                            let _ = ctx.reply("Não consegui transcrever esse áudio agora. Tente novamente ou envie por texto.").await;
                            return;
                        }
                    }
                } else {
                    return;
                };
                match result {
                    Ok(messages) => {
                        let sender = WaSender::new(ctx.client.clone(), http_client);
                        if let Err(error) = sender.send_to(&jid, &messages).await {
                            tracing::error!(%error, "envio");
                        }
                    }
                    Err(error) => {
                        tracing::error!(%error, "handler");
                        let _ = ctx.reply("Não consegui acessar o radar agora.").await;
                    }
                }
                let _ = ctx.client.chatstate().send_paused(&chat).await;
            }
        })
        .build()
        .await?;

        let client = bot.client();
        let handle = bot.spawn();
        if wait_for_pairing(&pairing, &client).await {
            break 'pareamento (client, handle);
        }
        tracing::warn!("QRs esgotados: subindo um cliente novo para oferecer QR de novo");
        handle.abort();
        tokio::time::sleep(Duration::from_secs(2)).await;
    };

    // Guarda o snapshot assim que pareia: sem isso, um restart nos primeiros
    // minutos perderia a sessão recém-criada e pediria QR de novo.
    match persist_session(&db, &cfg.session_path, client.is_logged_in()).await {
        Ok(true) => tracing::info!("snapshot inicial da sessão no Neon"),
        Ok(false) => {}
        Err(error) => tracing::warn!(%error, "snapshot inicial da sessão"),
    }

    let notify_db = db.clone();
    let notify_cfg = cfg.clone();
    let notify_http = http_client.clone();
    let notify_client = client.clone();
    let notify_task = tokio::spawn(async move {
        let sender = WaSender::new(notify_client, notify_http);
        loop {
            tokio::time::sleep(Duration::from_secs(30)).await;
            let now = now_maceio();
            if !due(now, read_stamp(&notify_cfg.notify_stamp_path)) {
                continue;
            }
            if let Err(error) = write_stamp(&notify_cfg.notify_stamp_path, now.date_naive()) {
                tracing::error!(%error, "stamp da notificação");
                continue;
            }
            tracing::info!("notificação diária");
            if let Err(error) = run_daily(&notify_db, &sender, &notify_cfg).await {
                tracing::error!(%error, "notificação");
            }
        }
    });

    // Backup periódico da sessão para o Neon — anti-repair se o container for
    // recriado (o free não tem disco persistente). O snapshot é consistente
    // (VACUUM INTO), não uma cópia crua do .db.
    let backup_db = db.clone();
    let backup_path = cfg.session_path.clone();
    let backup_client = client.clone();
    let backup_task = tokio::spawn(async move {
        loop {
            // 5 min.
            tokio::time::sleep(Duration::from_secs(300)).await;
            // Estado lido no momento do snapshot: um snapshot deslogado nunca
            // sobrescreve um logado no Neon (ver save_session_backup).
            let logged_in = backup_client.is_logged_in();
            match persist_session(&backup_db, &backup_path, logged_in).await {
                Ok(true) => tracing::debug!(logged_in, "backup da sessão no Neon"),
                Ok(false) => tracing::warn!(
                    "snapshot deslogado ignorado: já existe um snapshot logado no Neon"
                ),
                Err(error) => tracing::warn!(%error, "backup da sessão no Neon"),
            }
        }
    });

    wait_for_shutdown().await;
    tracing::info!("encerrando");
    // Ordem importa: o "logado" é lido ANTES de fechar o cliente (o snapshot
    // final precisa sair marcado como logado para valer), o cliente fecha em
    // seguida (checkpoint do WAL) e só então o snapshot é tirado — com o SQLite
    // já quieto.
    let was_logged_in = client.is_logged_in();
    handle.shutdown().await;
    match persist_session(&db, &cfg.session_path, was_logged_in).await {
        Ok(true) => tracing::info!(logged_in = was_logged_in, "backup final da sessão no Neon"),
        Ok(false) => tracing::warn!(
            "backup final ignorado: já existe um snapshot logado no Neon mais recente"
        ),
        Err(error) => tracing::error!(%error, "backup final da sessão no Neon"),
    }
    // Libera o lock só depois do backup: a próxima instância restaura o estado
    // mais novo antes de subir o cliente.
    if let Some(lock) = session_lock {
        db.unlock_session(lock).await;
    }
    notify_task.abort();
    http_task.abort();
    ping_task.abort();
    backup_task.abort();
    Ok(())
}

/// Snapshot consistente da sessão + gravação no Neon.
///
/// `VACUUM INTO` é I/O de arquivo e roda no pool de threads bloqueantes para não
/// travar o runtime async.
async fn persist_session(db: &Db, session_path: &str, logged_in: bool) -> anyhow::Result<bool> {
    let src = session_path.to_string();
    let tmp = snapshot_path(session_path);
    let bytes = tokio::task::spawn_blocking(move || snapshot_sqlite(&src, &tmp)).await??;
    if bytes.is_empty() {
        anyhow::bail!("snapshot da sessão vazio");
    }
    db.save_session_backup(&bytes, logged_in).await
}

/// Espera (com prazo) pelo lock da sessão do WhatsApp.
///
/// Se outra instância o detém, é o deploy anterior ainda de pé — o Render manda
/// SIGTERM nele em seguida e o lock cai junto com o processo. Esgotado o prazo,
/// segue mesmo assim: uma conexão duplicada por segundos é menos ruim que um bot
/// morto, e o alerta avisa.
async fn acquire_session_lock(
    db: &Db,
    cfg: &Arc<Config>,
) -> Option<SessionLock> {
    let deadline = Instant::now() + Duration::from_secs(cfg.session_lock_wait_seconds);
    let mut warned = false;
    loop {
        match db.try_lock_session().await {
            Ok(Some(lock)) => {
                tracing::info!("lock da sessão do WhatsApp adquirido");
                return Some(lock);
            }
            Ok(None) => {
                if !warned {
                    tracing::warn!(
                        "outra instância detém a sessão do WhatsApp; aguardando o deploy anterior encerrar"
                    );
                    warned = true;
                }
            }
            Err(error) => tracing::warn!(%error, "tentar o lock da sessão do WhatsApp"),
        }
        if Instant::now() >= deadline {
            ops::alert(
                "⚠️ André (WhatsApp): não obtive o lock da sessão no prazo e vou seguir \
                 mesmo assim — risco de conexão duplicada durante o deploy.",
            )
            .await;
            return None;
        }
        tokio::time::sleep(Duration::from_secs(3)).await;
    }
}

async fn wait_for_pairing(pairing: &Pairing, client: &Arc<Client>) -> bool {
    loop {
        tokio::time::sleep(Duration::from_secs(5)).await;
        if client.is_logged_in() {
            return true;
        }
        if pairing.is_exhausted() {
            return false;
        }
    }
}

async fn wait_for_shutdown() {
    let ctrl_c = async {
        let _ = tokio::signal::ctrl_c().await;
    };
    #[cfg(unix)]
    let terminate = async {
        if let Ok(mut signal) =
            tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        {
            signal.recv().await;
        }
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();
    tokio::select! {
        _ = ctrl_c => {}
        _ = terminate => {}
    }
}
