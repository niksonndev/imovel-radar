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
    raw: Option<bool>,
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
    // ?raw=1 → PNG a secas (para tools/curl).
    if query.raw == Some(true) {
        let Some(code) = state.pairing.qr() else {
            return (
                StatusCode::SERVICE_UNAVAILABLE,
                "Ainda sem QR. A página refresca sozinha.",
            )
                .into_response();
        };
        match qr_png(&code) {
            Ok(bytes) => return (
                StatusCode::OK,
                [(header::CONTENT_TYPE, "image/png")],
                bytes,
            )
                .into_response(),
            Err(error) => {
                tracing::error!(%error, "render do QR");
                return (StatusCode::INTERNAL_SERVER_ERROR, "Falha ao gerar o QR.").into_response()
            }
        }
    }
    // HTML que se auto-atualiza cada 5 s → sempre mostra um QR fresco,
    // evitando QR em cache/vencido (o pair-code flow expira em ~3 min).
    let page = format!(
        "<!doctype html><html lang=es><head><meta charset=utf-8>\
<meta http-equiv=refresh content=5>\
<title>Emparejar WhatsApp</title></head>\
<body style=\"background:#09090b;color:#e4e4e7;font-family:sans-serif;text-align:center;margin:32px\">\
<p style=\"opacity:.8\">Escaneá este QR con WhatsApp &gt; Dispositivos vinculados.<br>\
La página se refresca sola y siempre muestra el QR actual.</p>\
<img src=\"/pair?token={token}&amp;raw=1\" alt=\"QR\" \
style=\"width:340px;height:340px;image-rendering:pixelated;border-radius:12px;border:1px solid #333\">\
</body></html>",
        token = &query.token,
    );
    (
        StatusCode::OK,
        [(header::CONTENT_TYPE, "text/html; charset=utf-8")],
        page,
    )
        .into_response()
}
