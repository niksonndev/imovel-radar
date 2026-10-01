//! Registro de eventos operacionais críticos para observabilidade.

/// Avisa sobre um evento crítico de sessão. Nunca falha para o chamador: o
/// alerta é observabilidade, não pode derrubar o fluxo que o disparou.
pub async fn alert(text: &str) {
    tracing::error!(%text, "alerta de sessão");
}
