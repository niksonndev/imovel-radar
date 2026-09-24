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
    let Some(code) = state.pairing.qr() else {
        return (
            StatusCode::SERVICE_UNAVAILABLE,
            "Ainda sem QR. Espere o processo conectar e atualize.",
        )
            .into_response();
    };
    match qr_png(&code) {
        Ok(bytes) => (
            StatusCode::OK,
            [(header::CONTENT_TYPE, "image/png")],
            bytes,
        )
            .into_response(),
        Err(error) => {
            tracing::error!(%error, "render do QR");
            (StatusCode::INTERNAL_SERVER_ERROR, "Falha ao gerar o QR.").into_response()
        }
    }
}
