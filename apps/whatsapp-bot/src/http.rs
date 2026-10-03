use std::sync::Arc;

use axum::extract::{Query, State};
use axum::http::{header, HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Deserialize;

use crate::config::{tokens_match, Config};
use crate::db::Db;
use crate::pagamentos;
use crate::wa::{qr_png, Pairing};

#[derive(Clone)]
struct AppState {
    pairing: Arc<Pairing>,
    pair_secret: String,
    db: Db,
    cfg: Arc<Config>,
    http: reqwest::Client,
}

#[derive(Deserialize)]
struct PairQuery {
    token: String,
    /// Qualquer presença de `raw` vale (`raw=1`, `raw=true`, `raw`).
    /// Não usar `Option<bool>`: o serde_urlencoded do axum só aceita
    /// literalmente `true`/`false`, então `raw=1` devolvia 400.
    raw: Option<String>,
}

#[derive(Deserialize)]
struct WebhookQuery {
    /// Formato antigo de notificação: `?topic=payment&id=123`.
    id: Option<String>,
}

pub async fn serve(
    port: u16,
    pairing: Arc<Pairing>,
    pair_secret: String,
    db: Db,
    cfg: Arc<Config>,
    http: reqwest::Client,
) -> anyhow::Result<()> {
    let app = Router::new()
        .route("/health", get(health))
        .route("/pair", get(pair))
        .route("/webhook/mercadopago", post(webhook_mercadopago))
        .with_state(AppState {
            pairing,
            pair_secret,
            db,
            cfg,
            http,
        });
    let listener = tokio::net::TcpListener::bind(("0.0.0.0", port)).await?;
    tracing::info!(%port, "http em 0.0.0.0");
    axum::serve(listener, app).await?;
    Ok(())
}

/// Saúde do serviço + estado do pareamento. Sempre 200 (o Render derrubaria o
/// container em loop se devolvesse 503), mas com o estado visível: um bot que
/// restaurou a sessão e mesmo assim está oferecendo QR aparece aqui.
async fn health(State(state): State<AppState>) -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(serde_json::json!({
            "status": "ok",
            "connected": state.pairing.is_connected(),
            "pairing_exhausted": state.pairing.is_exhausted(),
            "qr_available": state.pairing.fresh_qr().is_some(),
            "qr_seconds_left": state.pairing.qr_seconds_left(),
        })),
    )
}

/// Notificação do Mercado Pago.
///
/// Duas checagens antes de qualquer coisa: a assinatura (`x-signature`) prova
/// que veio deles, e `processar_pagamento` confirma o status na API — a
/// notificação em si não é prova de pagamento. Sem isso, um POST com JSON
/// inventado viraria assinatura grátis.
async fn webhook_mercadopago(
    State(state): State<AppState>,
    Query(query): Query<WebhookQuery>,
    headers: HeaderMap,
    body: String,
) -> Response {
    let notificacao: pagamentos::NotificacaoWebhook =
        serde_json::from_str(&body).unwrap_or(pagamentos::NotificacaoWebhook {
            kind: None,
            action: None,
            data: None,
        });
    let Some(payment_id) = pagamentos::payment_id_da_notificacao(&notificacao, query.id.as_deref())
    else {
        // Evento que não é de pagamento: responder 200 para o PSP não reenviar.
        return StatusCode::OK.into_response();
    };
    let mp = pagamentos::MercadoPago::from_config(&state.cfg, state.http.clone());
    let assinatura = headers
        .get("x-signature")
        .and_then(|value| value.to_str().ok())
        .unwrap_or_default();
    let request_id = headers
        .get("x-request-id")
        .and_then(|value| value.to_str().ok());
    if !pagamentos::assinatura_valida(assinatura, request_id, &payment_id, mp.webhook_secret()) {
        tracing::warn!(payment_id, "webhook recusado: assinatura inválida");
        return StatusCode::UNAUTHORIZED.into_response();
    }
    match pagamentos::processar_pagamento(&state.db, &mp, &payment_id).await {
        Ok(resultado) => {
            tracing::info!(?resultado, payment_id, "webhook de pagamento");
            StatusCode::OK.into_response()
        }
        Err(error) => {
            // 5xx faz o PSP reenviar; a reconferência manual ("já paguei")
            // também cobre um webhook perdido durante o deploy.
            tracing::error!(%error, payment_id, "falha ao processar webhook");
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
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
                    .into_response();
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
