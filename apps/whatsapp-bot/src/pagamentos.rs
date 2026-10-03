//! Cobrança do Radar Pro via Mercado Pago (Checkout Pro: Pix e cartão no mesmo
//! link).
//!
//! O desenho tem três regras que não podem ser quebradas:
//!
//! 1. **Nada de dado de pagamento no chat.** O bot só manda um link; a página do
//!    PSP cuida do Pix/cartão. O prompt do assistente já proíbe pedir cartão.
//! 2. **Notificação não é prova de pagamento.** O webhook diz que *algo*
//!    aconteceu; a confirmação vem de `GET /v1/payments/{id}` com o nosso token,
//!    conferindo `status`, `external_reference` e valor. Sem essa segunda
//!    chamada, qualquer um poderia postar um JSON e virar Pro.
//! 3. **Ativação é idempotente.** Quem marca o pagamento como pago é um `UPDATE
//!    ... WHERE status = 'pendente' RETURNING`; notificação repetida não estende
//!    o Pro de novo.

use std::time::Duration;

use anyhow::{anyhow, Context};
use hmac::{Hmac, Mac};
use serde::Deserialize;
use serde_json::json;
use sha2::Sha256;

use crate::config::Config;

pub const PROVIDER: &str = "mercadopago";
const MP_API: &str = "https://api.mercadopago.com";

/// Prefixo da referência enviada ao PSP. Formato: `wa:<chat_id>:<token>`.
const REF_PREFIX: &str = "wa";

pub fn nova_referencia(chat_id: i64, token: &str) -> String {
    format!("{REF_PREFIX}:{chat_id}:{token}")
}

/// chat_id embutido na referência — é assim que o webhook sabe de quem é o
/// pagamento sem login nem código digitado pela pessoa.
pub fn chat_id_da_referencia(referencia: &str) -> Option<i64> {
    let mut parts = referencia.split(':');
    let prefix = parts.next()?;
    let chat = parts.next()?;
    if prefix != REF_PREFIX {
        return None;
    }
    chat.parse::<i64>().ok()
}

/// Token usado no `back_url` do checkout: só serve para reconhecer a volta.
pub fn token_aleatorio() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|value| value.as_nanos())
        .unwrap_or(0);
    format!("{nanos:x}{:x}", std::process::id())
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Plano {
    /// Id curto usado no botão e no `match` do passo ("1", "2").
    pub id: &'static str,
    pub titulo: &'static str,
    pub valor_centavos: i64,
    pub dias: i64,
}

/// Preços e durações dos planos, separados da `Config` para o catálogo ser
/// testável sem montar configuração inteira.
#[derive(Debug, Clone, Copy)]
pub struct PrecosPlanos {
    pub mensal_cents: i64,
    pub mensal_days: i64,
    pub semestral_cents: i64,
    pub semestral_days: i64,
}

impl PrecosPlanos {
    pub fn da_config(cfg: &Config) -> Self {
        Self {
            mensal_cents: cfg.pro_mensal_cents,
            mensal_days: cfg.pro_mensal_days,
            semestral_cents: cfg.pro_semestral_cents,
            semestral_days: cfg.pro_semestral_days,
        }
    }
}

/// Catálogo de planos pagos. R$ 19,90/mês e R$ 99,99/6 meses.
pub fn planos(precos: PrecosPlanos) -> Vec<Plano> {
    vec![
        Plano {
            id: "1",
            titulo: "Radar Pro — 1 mês",
            valor_centavos: precos.mensal_cents,
            dias: precos.mensal_days,
        },
        Plano {
            id: "2",
            titulo: "Radar Pro — 6 meses",
            valor_centavos: precos.semestral_cents,
            dias: precos.semestral_days,
        },
    ]
}

pub fn plano_por_id(precos: PrecosPlanos, id: &str) -> Option<Plano> {
    planos(precos)
        .into_iter()
        .find(|plano| plano.id == id.trim())
}

/// "R$ 19,90" a partir de centavos.
///
/// `money::format_brl` trabalha em reais inteiros; preço de plano tem centavos,
/// e valor de preço escrito errado é o tipo de erro que ninguém percebe no chat.
pub fn format_centavos(valor_centavos: i64) -> String {
    let reais = valor_centavos / 100;
    let centavos = (valor_centavos % 100).abs();
    let mut invertido: Vec<char> = reais.abs().to_string().chars().collect();
    invertido.reverse();
    let mut agrupado = String::new();
    for (index, ch) in invertido.iter().enumerate() {
        if index > 0 && index % 3 == 0 {
            agrupado.push('.');
        }
        agrupado.push(*ch);
    }
    let agrupado: String = agrupado.chars().rev().collect();
    let sinal = if valor_centavos < 0 { "-" } else { "" };
    format!("{sinal}R$ {agrupado},{centavos:02}")
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PagamentoEsperado {
    pub referencia: String,
    pub valor_centavos: i64,
    pub dias: i64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PagamentoNotificado {
    pub id: String,
    pub status: String,
    pub referencia: Option<String>,
    pub valor_centavos: i64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Decisao {
    /// Pode ativar; o valor diz por quantos dias.
    Ativar { dias: i64 },
    /// Nada a fazer (ainda não pago, ou já tratado).
    Ignorar(&'static str),
    /// Pagamento pago que não confere com a cobrança: registrar e não ativar.
    Recusar(&'static str),
}

/// Decide a ativação a partir do pagamento confirmado na API do PSP.
///
/// Puro de propósito: é a regra que dá dinheiro, então precisa de teste sem
/// rede. `aprovado` é o status do PSP; só `approved` ativa.
pub fn decidir_ativacao(notificado: &PagamentoNotificado, esperado: &PagamentoEsperado) -> Decisao {
    if notificado.status != "approved" {
        return Decisao::Ignorar("pagamento ainda não aprovado");
    }
    match notificado.referencia.as_deref() {
        Some(referencia) if referencia == esperado.referencia => {}
        Some(_) => return Decisao::Recusar("referência diferente da cobrança"),
        None => return Decisao::Recusar("pagamento sem referência"),
    }
    // Tolerância zero para menos; pagou a mais é problema do PSP, não nosso.
    if notificado.valor_centavos < esperado.valor_centavos {
        return Decisao::Recusar("valor abaixo do combinado");
    }
    Decisao::Ativar {
        dias: esperado.dias,
    }
}

/// Valida a origem da notificação (`x-signature: ts=...,v1=...`).
///
/// Manifesto conforme a documentação do Mercado Pago (o `data.id` entra em
/// minúsculas): `id:<data.id>;request-id:<x-request-id>;ts:<ts>;`. A comparação
/// é feita byte a byte pelo `verify_slice`, que já é resistente a timing.
pub fn assinatura_valida(
    x_signature: &str,
    x_request_id: Option<&str>,
    data_id: &str,
    secret: &str,
) -> bool {
    if secret.is_empty() {
        // Sem segredo configurado não há como provar origem: recusa em vez de
        // aceitar qualquer coisa.
        return false;
    }
    let mut ts: Option<&str> = None;
    let mut v1: Option<&str> = None;
    for part in x_signature.split(',') {
        let mut kv = part.trim().splitn(2, '=');
        match (kv.next(), kv.next()) {
            (Some("ts"), Some(value)) => ts = Some(value),
            (Some("v1"), Some(value)) => v1 = Some(value),
            _ => {}
        }
    }
    let (Some(ts), Some(v1)) = (ts, v1) else {
        return false;
    };
    let mut partes = vec![format!("id:{}", data_id.to_lowercase())];
    if let Some(request_id) = x_request_id {
        if !request_id.is_empty() {
            partes.push(format!("request-id:{request_id}"));
        }
    }
    partes.push(format!("ts:{ts}"));
    let manifest = format!("{};", partes.join(";"));
    let Ok(mut mac) = Hmac::<Sha256>::new_from_slice(secret.as_bytes()) else {
        return false;
    };
    mac.update(manifest.as_bytes());
    let Ok(decodificado) = hex_bytes(v1) else {
        return false;
    };
    // `verify_slice` compara em tempo constante.
    mac.verify_slice(&decodificado).is_ok()
}

fn hex_bytes(value: &str) -> Result<Vec<u8>, ()> {
    let value = value.trim();
    if value.len() % 2 != 0 {
        return Err(());
    }
    let mut out = Vec::with_capacity(value.len() / 2);
    let bytes = value.as_bytes();
    for pair in bytes.chunks(2) {
        let hi = (pair[0] as char).to_digit(16).ok_or(())?;
        let lo = (pair[1] as char).to_digit(16).ok_or(())?;
        out.push((hi * 16 + lo) as u8);
    }
    Ok(out)
}

pub fn hex_encode(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push_str(&format!("{byte:02x}"));
    }
    out
}

pub struct MercadoPago {
    http: reqwest::Client,
    access_token: String,
    webhook_secret: String,
    /// Base pública do bot, para o PSP saber onde notificar e para onde voltar.
    base_url: String,
    site_url: String,
}

impl MercadoPago {
    pub fn from_config(cfg: &Config, http: reqwest::Client) -> Self {
        Self {
            http,
            access_token: cfg.mp_access_token.clone(),
            webhook_secret: cfg.mp_webhook_secret.clone(),
            base_url: cfg.render_external_url.trim_end_matches('/').to_string(),
            site_url: cfg.public_site_url.trim_end_matches('/').to_string(),
        }
    }

    /// Configurado o suficiente para cobrar? Sem token, o fluxo avisa que
    /// pagamento ainda não está disponível em vez de gerar link quebrado.
    pub fn habilitado(&self) -> bool {
        !self.access_token.is_empty()
    }

    pub fn webhook_secret(&self) -> &str {
        &self.webhook_secret
    }

    /// Cria a preferência e devolve a URL do checkout hospedado (Pix e cartão).
    pub async fn criar_preferencia(
        &self,
        referencia: &str,
        valor_centavos: i64,
        dias: i64,
        titulo: &str,
    ) -> anyhow::Result<String> {
        if !self.habilitado() {
            return Err(anyhow!("mercadopago sem access token"));
        }
        let unit_price = valor_centavos as f64 / 100.0;
        let payload = json!({
            "items": [{
                "title": titulo,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": unit_price,
            }],
            "external_reference": referencia,
            "notification_url": format!("{}/webhook/mercadopago", self.base_url),
            "back_urls": {
                "success": format!("{}/assinar/obrigado", self.site_url),
                "pending": format!("{}/assinar/pendente", self.site_url),
                "failure": format!("{}/assinar/falhou", self.site_url),
            },
            "auto_return": "approved",
            "statement_descriptor": "ANDRE RADAR",
            "metadata": {"dias": dias},
        });
        let response = self
            .http
            .post(format!("{MP_API}/checkout/preferences"))
            .bearer_auth(&self.access_token)
            .json(&payload)
            .timeout(Duration::from_secs(20))
            .send()
            .await
            .context("criar preferência")?;
        let status = response.status();
        let body: serde_json::Value = response.json().await.unwrap_or_default();
        if !status.is_success() {
            return Err(anyhow!(
                "mercadopago {} ao criar preferência: {}",
                status,
                body.to_string().chars().take(300).collect::<String>()
            ));
        }
        let url = body["init_point"]
            .as_str()
            .or_else(|| body["sandbox_init_point"].as_str())
            .ok_or_else(|| anyhow!("preferência sem init_point"))?;
        Ok(url.to_string())
    }

    /// Pagamentos de uma cobrança, direto da API.
    ///
    /// É a rede de segurança do webhook: se a notificação se perder (deploy,
    /// container dormindo), a pessoa pode responder "já paguei" e o bot
    /// reconfere por aqui em vez de mandar ela pagar de novo.
    pub async fn buscar_por_referencia(
        &self,
        referencia: &str,
    ) -> anyhow::Result<Vec<PagamentoNotificado>> {
        if !self.habilitado() {
            return Err(anyhow!("mercadopago sem access token"));
        }
        let response = self
            .http
            .get(format!("{MP_API}/v1/payments/search"))
            .bearer_auth(&self.access_token)
            .query(&[("external_reference", referencia)])
            .timeout(Duration::from_secs(20))
            .send()
            .await
            .context("buscar pagamentos")?;
        let status = response.status();
        let body: serde_json::Value = response.json().await.unwrap_or_default();
        if !status.is_success() {
            return Err(anyhow!(
                "mercadopago {} ao buscar pagamentos: {}",
                status,
                body.to_string().chars().take(200).collect::<String>()
            ));
        }
        Ok(body["results"]
            .as_array()
            .map(|results| results.iter().map(parse_pagamento).collect())
            .unwrap_or_default())
    }

    /// Confirma o pagamento na API do PSP (a notificação sozinha não prova nada).
    pub async fn buscar_pagamento(&self, payment_id: &str) -> anyhow::Result<PagamentoNotificado> {
        if !self.habilitado() {
            return Err(anyhow!("mercadopago sem access token"));
        }
        let response = self
            .http
            .get(format!("{MP_API}/v1/payments/{payment_id}"))
            .bearer_auth(&self.access_token)
            .timeout(Duration::from_secs(20))
            .send()
            .await
            .context("consultar pagamento")?;
        let status = response.status();
        let body: serde_json::Value = response.json().await.unwrap_or_default();
        if !status.is_success() {
            return Err(anyhow!(
                "mercadopago {} ao consultar pagamento: {}",
                status,
                body.to_string().chars().take(200).collect::<String>()
            ));
        }
        Ok(parse_pagamento(&body))
    }
}

/// `transaction_amount` vem em reais com centavos; arredonda para centavos.
pub fn parse_pagamento(body: &serde_json::Value) -> PagamentoNotificado {
    let valor = body["transaction_amount"]
        .as_f64()
        .map(|value| (value * 100.0).round() as i64)
        .unwrap_or(0);
    PagamentoNotificado {
        id: body["id"]
            .as_i64()
            .map(|value| value.to_string())
            .or_else(|| body["id"].as_str().map(str::to_string))
            .unwrap_or_default(),
        status: body["status"].as_str().unwrap_or_default().to_string(),
        referencia: body["external_reference"].as_str().map(str::to_string),
        valor_centavos: valor,
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ResultadoPagamento {
    /// Pro ligado agora (primeira confirmação desta cobrança).
    Ativado { dias: i64 },
    /// O PSP ainda não aprovou.
    Pendente,
    /// Já tinha sido contabilizado antes (webhook repetido).
    JaContabilizado,
    /// Pago, mas não confere com a cobrança registrada.
    Recusado,
    /// Nada a fazer (evento que não é deste fluxo).
    Ignorado,
}

/// Confirma o pagamento na API do PSP e, se estiver tudo certo, liga o Pro.
///
/// É o único caminho de ativação: usado pelo webhook e pela reconferência
/// manual ("já paguei"), para um webhook perdido no deploy não deixar ninguém
/// pagando sem receber.
pub async fn processar_pagamento(
    db: &crate::db::Db,
    mp: &MercadoPago,
    payment_id: &str,
) -> anyhow::Result<ResultadoPagamento> {
    let notificado = mp.buscar_pagamento(payment_id).await?;
    let Some(referencia) = notificado.referencia.clone() else {
        tracing::warn!(payment_id, "pagamento sem external_reference");
        return Ok(ResultadoPagamento::Ignorado);
    };
    let Some(pagamento) = db.pagamento_por_referencia(&referencia).await? else {
        tracing::warn!(%referencia, "pagamento de referência desconhecida");
        return Ok(ResultadoPagamento::Ignorado);
    };
    let esperado = PagamentoEsperado {
        referencia: pagamento.referencia.clone(),
        valor_centavos: pagamento.valor_centavos,
        dias: pagamento.dias,
    };
    match decidir_ativacao(&notificado, &esperado) {
        Decisao::Ativar { .. } => {
            match db.confirmar_pagamento(&referencia, &notificado.id).await? {
                Some((chat_id, dias)) => {
                    tracing::info!(chat_id, dias, "pro ativado por pagamento");
                    Ok(ResultadoPagamento::Ativado { dias })
                }
                None => Ok(ResultadoPagamento::JaContabilizado),
            }
        }
        Decisao::Ignorar(_) => Ok(ResultadoPagamento::Pendente),
        Decisao::Recusar(motivo) => {
            tracing::warn!(%referencia, motivo, "pagamento recusado");
            db.marcar_pagamento_recusado(&referencia).await?;
            Ok(ResultadoPagamento::Recusado)
        }
    }
}

/// Reconferência manual de uma cobrança ("já paguei").
pub async fn processar_referencia(
    db: &crate::db::Db,
    mp: &MercadoPago,
    referencia: &str,
) -> anyhow::Result<ResultadoPagamento> {
    let Some(pagamento) = db.pagamento_por_referencia(referencia).await? else {
        return Ok(ResultadoPagamento::Ignorado);
    };
    if pagamento.status == "pago" {
        return Ok(ResultadoPagamento::JaContabilizado);
    }
    let esperado = PagamentoEsperado {
        referencia: pagamento.referencia.clone(),
        valor_centavos: pagamento.valor_centavos,
        dias: pagamento.dias,
    };
    for notificado in mp.buscar_por_referencia(referencia).await? {
        if !matches!(decidir_ativacao(&notificado, &esperado), Decisao::Ativar { .. }) {
            continue;
        }
        return match db.confirmar_pagamento(referencia, &notificado.id).await? {
            Some((chat_id, dias)) => {
                tracing::info!(chat_id, dias, "pro ativado por reconferência");
                Ok(ResultadoPagamento::Ativado { dias })
            }
            None => Ok(ResultadoPagamento::JaContabilizado),
        };
    }
    Ok(ResultadoPagamento::Pendente)
}

#[derive(Debug, Deserialize)]
pub struct NotificacaoWebhook {
    #[serde(rename = "type")]
    pub kind: Option<String>,
    pub action: Option<String>,
    pub data: Option<NotificacaoData>,
}

#[derive(Debug, Deserialize)]
pub struct NotificacaoData {
    pub id: Option<String>,
}

/// Id do pagamento dentro da notificação, aceitando o formato novo (`data.id`)
/// e o antigo por query (`?topic=payment&id=`).
pub fn payment_id_da_notificacao(
    notificacao: &NotificacaoWebhook,
    query_id: Option<&str>,
) -> Option<String> {
    if let Some(kind) = notificacao.kind.as_deref() {
        if kind != "payment" {
            return None;
        }
    }
    notificacao
        .data
        .as_ref()
        .and_then(|data| data.id.clone())
        .filter(|id| !id.is_empty())
        .or_else(|| query_id.map(str::to_string).filter(|id| !id.is_empty()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use hmac::Mac;

    fn referencia() -> String {
        nova_referencia(5511999999999, "abc123")
    }

    #[test]
    fn referencia_carrega_o_chat_id() {
        assert_eq!(chat_id_da_referencia(&referencia()), Some(5511999999999));
        assert_eq!(chat_id_da_referencia("wa:nao-numero:x"), None);
        assert_eq!(chat_id_da_referencia("outro:1:x"), None);
        assert_eq!(chat_id_da_referencia(""), None);
    }

    #[test]
    fn formata_preco_em_centavos() {
        assert_eq!(format_centavos(1990), "R$ 19,90");
        assert_eq!(format_centavos(9999), "R$ 99,99");
        assert_eq!(format_centavos(199000), "R$ 1.990,00");
        assert_eq!(format_centavos(100), "R$ 1,00");
        assert_eq!(format_centavos(5), "R$ 0,05");
        assert_eq!(format_centavos(-1990), "-R$ 19,90");
    }

    #[test]
    fn catalogo_tem_mensal_e_semestral() {
        let precos = PrecosPlanos {
            mensal_cents: 1990,
            mensal_days: 30,
            semestral_cents: 9999,
            semestral_days: 180,
        };
        let planos = planos(precos);
        assert_eq!(planos.len(), 2);
        assert_eq!(planos[0].valor_centavos, 1990);
        assert_eq!(planos[0].dias, 30);
        assert_eq!(planos[1].valor_centavos, 9999);
        assert_eq!(planos[1].dias, 180);
        assert_eq!(
            plano_por_id(precos, "2").map(|plano| plano.valor_centavos),
            Some(9999)
        );
        assert!(plano_por_id(precos, "9").is_none());
    }

    #[test]
    fn assinatura_aceita_manifesto_correto() {
        let secret = "segredo-de-teste";
        let data_id = "ABC-123";
        let request_id = "req-1";
        let ts = "1700000000";
        let manifest = format!("id:{};request-id:{request_id};ts:{ts};", data_id.to_lowercase());
        let mut mac = Hmac::<Sha256>::new_from_slice(secret.as_bytes()).unwrap();
        mac.update(manifest.as_bytes());
        let v1 = hex_encode(&mac.finalize().into_bytes());
        let header = format!("ts={ts},v1={v1}");
        assert!(assinatura_valida(&header, Some(request_id), data_id, secret));
        // Id em maiúsculas não muda o resultado: o manifesto usa minúsculas.
        assert!(assinatura_valida(&header, Some(request_id), "abc-123", secret));
    }

    #[test]
    fn assinatura_recusa_o_que_nao_confere() {
        let secret = "segredo-de-teste";
        let header = "ts=1700000000,v1=deadbeef";
        assert!(!assinatura_valida(header, Some("req-1"), "1", secret));
        // Sem segredo configurado, ninguém entra.
        assert!(!assinatura_valida(header, Some("req-1"), "1", ""));
        // Header malformado.
        assert!(!assinatura_valida("v1=deadbeef", None, "1", secret));
        assert!(!assinatura_valida("", None, "1", secret));
        // v1 que não é hex.
        assert!(!assinatura_valida("ts=1,v1=zz", Some("r"), "1", secret));
        // Assinatura de outro request id (troca de contexto).
        let ts = "1700000000";
        let manifest = format!("id:1;request-id:correto;ts:{ts};");
        let mut mac = Hmac::<Sha256>::new_from_slice(secret.as_bytes()).unwrap();
        mac.update(manifest.as_bytes());
        let header = format!("ts={ts},v1={}", hex_encode(&mac.finalize().into_bytes()));
        assert!(!assinatura_valida(&header, Some("outro"), "1", secret));
    }

    #[test]
    fn decisao_ativa_so_aprovado_e_conferindo() {
        let esperado = PagamentoEsperado {
            referencia: referencia(),
            valor_centavos: 1990,
            dias: 30,
        };
        let aprovado = PagamentoNotificado {
            id: "1".into(),
            status: "approved".into(),
            referencia: Some(referencia()),
            valor_centavos: 1990,
        };
        assert_eq!(
            decidir_ativacao(&aprovado, &esperado),
            Decisao::Ativar { dias: 30 }
        );

        let pendente = PagamentoNotificado {
            status: "pending".into(),
            ..aprovado.clone()
        };
        assert!(matches!(
            decidir_ativacao(&pendente, &esperado),
            Decisao::Ignorar(_)
        ));

        let outra_referencia = PagamentoNotificado {
            referencia: Some(nova_referencia(1, "x")),
            ..aprovado.clone()
        };
        assert!(matches!(
            decidir_ativacao(&outra_referencia, &esperado),
            Decisao::Recusar(_)
        ));

        let sem_referencia = PagamentoNotificado {
            referencia: None,
            ..aprovado.clone()
        };
        assert!(matches!(
            decidir_ativacao(&sem_referencia, &esperado),
            Decisao::Recusar(_)
        ));

        let valor_menor = PagamentoNotificado {
            valor_centavos: 990,
            ..aprovado.clone()
        };
        assert!(matches!(
            decidir_ativacao(&valor_menor, &esperado),
            Decisao::Recusar(_)
        ));

        let valor_maior = PagamentoNotificado {
            valor_centavos: 2990,
            ..aprovado
        };
        assert_eq!(
            decidir_ativacao(&valor_maior, &esperado),
            Decisao::Ativar { dias: 30 }
        );
    }

    #[test]
    fn notificacao_aceita_formato_novo_e_antigo() {
        let nova: NotificacaoWebhook =
            serde_json::from_str(r#"{"action":"payment.updated","type":"payment","data":{"id":"123"}}"#)
                .unwrap();
        assert_eq!(payment_id_da_notificacao(&nova, None).as_deref(), Some("123"));

        let antiga: NotificacaoWebhook = serde_json::from_str("{}").unwrap();
        assert_eq!(
            payment_id_da_notificacao(&antiga, Some("456")).as_deref(),
            Some("456")
        );

        let outro: NotificacaoWebhook =
            serde_json::from_str(r#"{"type":"merchant_order","data":{"id":"9"}}"#).unwrap();
        assert_eq!(payment_id_da_notificacao(&outro, Some("456")), None);
    }

    #[test]
    fn parse_pagamento_converte_valor_e_id() {
        let body = serde_json::json!({
            "id": 987654,
            "status": "approved",
            "external_reference": "wa:42:tok",
            "transaction_amount": 19.9
        });
        let parsed = parse_pagamento(&body);
        assert_eq!(parsed.id, "987654");
        assert_eq!(parsed.status, "approved");
        assert_eq!(parsed.referencia.as_deref(), Some("wa:42:tok"));
        assert_eq!(parsed.valor_centavos, 1990);
        // Corpo vazio não entra em pânico nem inventa valor.
        let vazio = parse_pagamento(&serde_json::json!({}));
        assert_eq!(vazio.valor_centavos, 0);
        assert!(vazio.referencia.is_none());
    }
}
