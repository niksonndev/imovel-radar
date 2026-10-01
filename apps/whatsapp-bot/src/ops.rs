//! Alerta operacional opcional por Telegram.
//!
//! O próprio bot É o canal de WhatsApp: quando ele cai para o pareamento por QR
//! não há como avisar por WhatsApp. Se `OPS_ALERT_TELEGRAM_TOKEN` e
//! `OPS_ALERT_TELEGRAM_CHAT_ID` estiverem definidos, os eventos críticos de
//! sessão saem por Telegram; sem eles, ficam só no log (e no `/health`).

use std::sync::Arc;

use crate::config::Config;

/// Avisa sobre um evento crítico de sessão. Nunca falha para o chamador: o
/// alerta é observabilidade, não pode derrubar o fluxo que o disparou.
pub async fn alert(cfg: &Arc<Config>, http: &reqwest::Client, text: &str) {
    if !cfg.ops_alert_enabled() {
        tracing::error!(%text, "alerta de sessão (sem canal de alerta configurado)");
        return;
    }
    tracing::error!(%text, "alerta de sessão");
    let url = format!(
        "https://api.telegram.org/bot{}/sendMessage",
        cfg.ops_alert_telegram_token
    );
    let payload = serde_json::json!({
        "chat_id": cfg.ops_alert_telegram_chat_id,
        "text": text,
        "disable_web_page_preview": true,
    });
    match http.post(&url).json(&payload).send().await {
        Ok(response) if !response.status().is_success() => {
            tracing::warn!(
                status = response.status().as_u16(),
                "alerta operacional recusado"
            );
        }
        Ok(_) => {}
        Err(error) => tracing::warn!(%error, "enviar alerta operacional"),
    }
}
