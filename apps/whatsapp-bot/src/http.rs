use std::sync::Arc;

use axum::extract::{Query, State};
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use axum::Router;
use serde::Deserialize;

use crate::config::tokens_match;
use crate::wa::{qr_png, Pairing};

#[derive(Clone)]
struct AppState {
    pairing: Arc<Pairing>,
    pair_secret: String,
}

#[derive(Deserialize)]
struct PairQuery {
    token: String,
    /// Qualquer presença de `raw` vale (`raw=1`, `raw=true`, `raw`).
    /// Não usar `Option<bool>`: o serde_urlencoded do axum só aceita
    /// literalmente `true`/`false`, então `raw=1` devolvia 400.
    raw: Option<String>,
}

pub async fn serve(port: u16, pairing: Arc<Pairing>, pair_secret: String) -> anyhow::Result<()> {
    let app = Router::new()
        .route("/health", get(health))
        .route("/pair", get(pair))
        .with_state(AppState {
            pairing,
            pair_secret,
        });
    let listener = tokio::net::TcpListener::bind(("0.0.0.0", port)).await?;
    tracing::info!(%port, "http em 0.0.0.0");
    axum::serve(listener, app).await?;
    Ok(())
}

async fn health() -> &'static str {
    "ok"
}

async fn pair(State(state): State<AppState>, Query(query): Query<PairQuery>) -> Response {
    if state.pair_secret.is_empty() || !tokens_match(&query.token, &state.pair_secret) {
        return StatusCode::NOT_FOUND.into_response();
    }
    if state.pairing.is_connected() {
        return (StatusCode::OK, "Já pareado.").into_response();
    }
    // ?raw=1 → PNG puro (para curl/ferramentas).
    if query.raw.is_some() {
        let Some(code) = state.pairing.fresh_qr() else {
            return (
                StatusCode::SERVICE_UNAVAILABLE,
                "Sem QR válido agora. A página atualiza sozinha.",
            )
                .into_response();
        };
        match qr_png(&code) {
            Ok(bytes) => {
                return (
                    StatusCode::OK,
                    [
                        (header::CONTENT_TYPE, "image/png"),
                        // Sem cache: o QR muda e a URL da imagem é sempre a mesma.
                        (header::CACHE_CONTROL, "no-store, max-age=0"),
                    ],
                    bytes,
                )
                    .into_response()
            }
            Err(error) => {
                tracing::error!(%error, "render do QR");
                return (StatusCode::INTERNAL_SERVER_ERROR, "Falha ao gerar o QR.").into_response();
            }
        }
    }
    // HTML que se auto-atualiza a cada 5 s → sempre mostra o QR vigente.
    // Sem QR válido agora, mostra a etapa real em vez de uma imagem quebrada.
    let (qr_part, status) = match (state.pairing.fresh_qr(), state.pairing.qr_seconds_left()) {
        (Some(_), left) => (
            format!(
                "<img src=\"/pair?token={token}&amp;raw=1\" alt=\"QR\" \
style=\"width:340px;height:340px;image-rendering:pixelated;border-radius:12px;border:1px solid #333;margin-top:16px\">",
                token = &query.token,
            ),
            match left {
                Some(seconds) => format!("QR válido por ~{seconds} s."),
                None => String::new(),
            },
        ),
        (None, _) if state.pairing.is_exhausted() => (
            String::from(
                "<p style=\"opacity:.7;margin-top:24px\">Os QR anteriores expiraram sem pareamento.<br>\
Gerando um novo em instantes — esta página recarrega sozinha.</p>",
            ),
            String::new(),
        ),
        (None, _) => (
            String::from(
                "<p style=\"opacity:.7;margin-top:24px\">Conectando, preparando o QR...<br>\
(a página atualiza sozinha).</p>",
            ),
            String::new(),
        ),
    };
    let page = format!(
        "<!doctype html><html lang=pt-BR><head><meta charset=utf-8>\
<meta http-equiv=refresh content=5>\
<title>Vincular WhatsApp</title></head>\
<body style=\"background:#09090b;color:#e4e4e7;font-family:sans-serif;text-align:center;margin:32px\">\
<p style=\"opacity:.8\">Escaneie este QR com o WhatsApp &gt; Dispositivos conectados.<br>\
A página atualiza sozinha e sempre mostra o QR atual.</p>\
{status}\
{qr_part}\
</body></html>",
        status = if status.is_empty() {
            String::new()
        } else {
            format!("<p style=\"opacity:.8\">{status}</p>")
        },
        qr_part = qr_part,
    );
    (
        StatusCode::OK,
        [
            (header::CONTENT_TYPE, "text/html; charset=utf-8"),
            // Página com auto-refresh: não deixar cachear o HTML.
            (header::CACHE_CONTROL, "no-store, max-age=0"),
        ],
        page,
    )
        .into_response()
}
