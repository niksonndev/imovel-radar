use std::time::Duration;

use chrono::Utc;
use serde_json::{json, Value};

use crate::ai::{
    call_assistant_function, closest_neighbourhoods, draft_state, extract_alert_intent,
    match_neighbourhoods, mock_extract_alert, AssistantFunctionCall,
};
use crate::config::Config;
use crate::db::Db;
use crate::intelligence::prepare_match_carousel;
use crate::models::{Alert, ClaimStatus, CreateAlertStatus, Listing, WatchStatus};
use crate::money::{effective_listing_price, format_brl, json_fee};
use crate::pagamentos;
use crate::session::{
    global_command, normalize_text, parse_index_list, parse_money, parse_number_words, Draft,
    GlobalCommand, Session, Step,
};
use crate::ui::{
    alert_detail, alerts_list, auto_alert_name, cap_alerts, cap_watches, card_caption,
    categories_prompt, category_options, city_prompt, confirm_prompt, edit_stub, help_text,
    intent_prompt, kind_prompt, main_menu, name_prompt, neighbourhoods_prompt, pagamento_link,
    planos_prompt, price_max_prompt, price_min_prompt, price_presets, price_prompt, pro_activated,
    pro_pitch, rooms_prompt, watch_card_caption,
};
use crate::wa::interactive;

/// Botão de resposta rápida. O `id` é exatamente a opção que o roteador já
/// entende no texto, para o toque entrar no fluxo como se tivesse sido digitado.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Button {
    pub id: String,
    pub label: String,
}

#[derive(Debug, Clone)]
pub enum OutMsg {
    Text(String),
    Image {
        url: String,
        caption: String,
    },
    /// Texto com botões de resposta rápida. O WhatsApp aceita no máximo 3 e o
    /// corpo mantém as opções numeradas: se o cliente não renderizar os botões,
    /// a pessoa ainda responde digitando o número.
    Buttons {
        body: String,
        buttons: Vec<Button>,
    },
}

/// Legenda da navegação do carrossel (o número digitado sempre funciona).
const NAV_HINT: &str = "1 próximo · 2 anterior · 3 acompanhar · 4 menu";

fn text(body: impl Into<String>) -> OutMsg {
    OutMsg::Text(body.into())
}

fn button(id: &str, label: &str) -> Button {
    Button {
        id: id.to_string(),
        label: label.to_string(),
    }
}

fn buttons(body: String, items: Vec<Button>) -> OutMsg {
    OutMsg::Buttons {
        body,
        buttons: items,
    }
}

/// Rótulo de botão: o WhatsApp recomenda até 20 caracteres.
fn button_label(raw: &str) -> String {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return "Sem nome".to_string();
    }
    if trimmed.chars().count() <= 20 {
        return trimmed.to_string();
    }
    let mut label: String = trimmed.chars().take(19).collect();
    label.push('…');
    label
}

/// Menu principal: são exatamente as três opções do texto, então os botões
/// carregam o menu inteiro.
fn menu_message() -> OutMsg {
    buttons(
        main_menu(),
        vec![
            button("1", "Novo alerta"),
            button("2", "Meus alertas"),
            button("3", "Ajuda"),
        ],
    )
}

/// Confirmação do alerta: mesmos "1"/"2" que o roteador lê no texto.
fn confirm_message(draft: &Draft) -> OutMsg {
    buttons(
        confirm_prompt(draft),
        vec![button("1", "Confirmar"), button("2", "Cancelar")],
    )
}

/// Confirmação de remoção de um alerta.
fn confirm_removal_message(alert: &Alert) -> OutMsg {
    buttons(
        format!(
            "Confirma a remoção deste alerta?\n\n{}\n1. Confirmar remoção\n2. Cancelar",
            alert_detail(alert)
        ),
        vec![button("1", "Confirmar remoção"), button("2", "Cancelar")],
    )
}

/// Detalhe do alerta com as três ações como botões.
fn alert_detail_message(alert: &Alert) -> OutMsg {
    buttons(
        alert_detail(alert),
        vec![
            button("1", "Apagar"),
            button("2", "Editar"),
            button("3", "Voltar"),
        ],
    )
}

/// Editar ainda é stub; o botão é só a volta (id 3, que é o que o passo lê).
fn edit_stub_message(name: &str) -> OutMsg {
    buttons(edit_stub(name), vec![button("3", "Voltar")])
}

fn down() -> OutMsg {
    text("Não consegui acessar o radar agora. Tenta de novo em instantes.")
}

pub async fn handle_text(
    db: &Db,
    cfg: &Config,
    http: &reqwest::Client,
    chat_id: i64,
    raw: &str,
) -> anyhow::Result<Vec<OutMsg>> {
    handle_inbound(db, cfg, http, chat_id, raw, None, false).await
}

pub async fn handle_transcribed_audio(
    db: &Db,
    cfg: &Config,
    http: &reqwest::Client,
    chat_id: i64,
    raw: &str,
    duration_seconds: u32,
) -> anyhow::Result<Vec<OutMsg>> {
    handle_inbound(db, cfg, http, chat_id, raw, Some(duration_seconds), true).await
}

async fn handle_inbound(
    db: &Db,
    cfg: &Config,
    http: &reqwest::Client,
    chat_id: i64,
    raw: &str,
    audio_seconds: Option<u32>,
    quota_preconsumed: bool,
) -> anyhow::Result<Vec<OutMsg>> {
    let ttl = Duration::from_secs((cfg.session_ttl_hours.max(1) as u64) * 3600);
    let mut session = match db.load_session(chat_id, ttl).await {
        Ok(Some(session)) => session,
        Ok(None) => Session::menu(),
        Err(error) => {
            tracing::error!(%error, "falha ao ler sessão");
            return Ok(vec![down()]);
        }
    };
    let raw = raw.trim();
    if raw.is_empty() {
        session.step = Step::Menu;
        return store(db, chat_id, &session, vec![menu_message()]).await;
    }

    if let Some(command) = global_command(raw) {
        return on_global(db, cfg, http, chat_id, &mut session, command).await;
    }

    let step = session.step.clone();
    if raw.chars().count() > cfg.assistant_max_message_chars
        && matches!(
            step,
            Step::Menu | Step::Intent | Step::AssistantConversation
        )
    {
        return store(
            db,
            chat_id,
            &session,
            vec![text(format!(
                "Sua mensagem passou do limite de {} caracteres. Envie um trecho menor.",
                cfg.assistant_max_message_chars
            ))],
        )
        .await;
    }
    let messages = match step {
        Step::Menu => {
            on_menu(
                db,
                cfg,
                http,
                chat_id,
                &mut session,
                raw,
                audio_seconds,
                quota_preconsumed,
            )
            .await?
        }
        Step::Intent if cfg.llm_provider == "openai" && normalize_text(raw) != "1" => {
            assistant_turn(
                db,
                cfg,
                http,
                chat_id,
                &mut session,
                raw,
                audio_seconds,
                quota_preconsumed,
            )
            .await?
        }
        Step::Intent => on_intent(db, cfg, http, chat_id, &mut session, raw).await?,
        Step::AssistantConversation => {
            assistant_turn(
                db,
                cfg,
                http,
                chat_id,
                &mut session,
                raw,
                audio_seconds,
                quota_preconsumed,
            )
            .await?
        }
        Step::City => on_city(db, &mut session, raw).await?,
        Step::Kind => on_kind(&mut session, raw),
        Step::Categories => on_categories(&mut session, raw),
        Step::Price => on_price(&mut session, raw),
        Step::PriceMin => on_price_min(&mut session, raw),
        Step::PriceMax => on_price_max(&mut session, raw),
        Step::Rooms => on_rooms(db, &mut session, raw).await?,
        Step::Neighbourhoods { page } => on_neighbourhoods(db, &mut session, raw, page).await?,
        Step::Name => on_name(&mut session, raw),
        Step::Confirm => finish_alert(db, cfg, chat_id, &mut session, raw).await?,
        Step::Alerts { ids: _ } if raw.trim().parse::<usize>().is_err() => {
            assistant_turn(
                db,
                cfg,
                http,
                chat_id,
                &mut session,
                raw,
                audio_seconds,
                quota_preconsumed,
            )
            .await?
        }
        Step::Alerts { ids } => on_alerts(db, cfg, chat_id, &mut session, raw, &ids).await?,
        Step::AlertDetail { id: _ } if !matches!(raw.trim(), "1" | "2" | "3") => {
            assistant_turn(
                db,
                cfg,
                http,
                chat_id,
                &mut session,
                raw,
                audio_seconds,
                quota_preconsumed,
            )
            .await?
        }
        Step::AlertDetail { id } => on_alert_detail(db, chat_id, &mut session, raw, id).await?,
        Step::AssistantRemoveChoice { ids } => {
            on_assistant_remove_choice(db, chat_id, &mut session, raw, &ids).await?
        }
        Step::AssistantDeleteConfirm { id } => {
            on_assistant_delete_confirm(db, chat_id, &mut session, raw, id).await?
        }
        Step::DeleteAccountConfirm => {
            on_delete_account_confirm(db, chat_id, &mut session, raw).await?
        }
        Step::Deleted => vec![text("Seus dados foram excluídos.")],
        Step::Email => on_email(db, cfg, chat_id, &mut session, raw).await?,
        Step::Assinar => on_assinar_plano(db, cfg, http, chat_id, &mut session, raw).await?,
        Step::MatchCarousel { index, listing_ids } => {
            on_match_carousel(db, cfg, chat_id, &mut session, raw, index, &listing_ids).await?
        }
        Step::WatchCarousel { index, watch_ids } => {
            on_watch_carousel(db, chat_id, &mut session, raw, index, &watch_ids).await?
        }
    };
    store(db, chat_id, &session, messages).await
}

async fn store(
    db: &Db,
    chat_id: i64,
    session: &Session,
    messages: Vec<OutMsg>,
) -> anyhow::Result<Vec<OutMsg>> {
    if matches!(session.step, Step::Deleted) {
        if let Err(error) = db.clear_session(chat_id).await {
            tracing::error!(%error, "limpar sessão após exclusão");
        }
        return Ok(messages);
    }
    if let Err(error) = db.save_session(chat_id, session).await {
        tracing::error!(%error, "falha ao gravar sessão");
    }
    Ok(messages)
}

async fn on_global(
    db: &Db,
    cfg: &Config,
    http: &reqwest::Client,
    chat_id: i64,
    session: &mut Session,
    command: GlobalCommand,
) -> anyhow::Result<Vec<OutMsg>> {
    let messages = match command {
        GlobalCommand::Menu => {
            *session = Session::menu();
            vec![menu_message()]
        }
        GlobalCommand::Cancel => {
            let in_flow = !matches!(session.step, Step::Menu);
            *session = Session::menu();
            if in_flow {
                vec![text("Criação cancelada."), menu_message()]
            } else {
                vec![menu_message()]
            }
        }
        GlobalCommand::Help => {
            session.step = Step::Menu;
            vec![text(help_text()), menu_message()]
        }
        GlobalCommand::NewAlert => start_alert(cfg, session),
        GlobalCommand::MyAlerts => list_alerts(db, chat_id, session).await?,
        GlobalCommand::Watching => list_watches(db, chat_id, session).await?,
        GlobalCommand::Pro => on_assinatura(db, cfg, http, chat_id, session).await?,
        GlobalCommand::Paguei => on_ja_paguei(db, cfg, http, chat_id, session).await?,
        GlobalCommand::Privacy => vec![text(format!(
            "Privacidade e uso dos dados: {}/privacidade\nTermos: {}/termos\n\nPara solicitar a exclusão dos dados, digite *excluir dados*.",
            cfg.public_site_url, cfg.public_site_url
        ))],
        GlobalCommand::DeleteData => {
            session.draft = Draft::default();
            session.step = Step::DeleteAccountConfirm;
            vec![text("A exclusão remove sua conta WhatsApp, alertas, anúncios acompanhados, e-mail do trial e memória curta. Mensagens já enviadas continuam no histórico do WhatsApp. Para confirmar, responda *EXCLUIR*. Para cancelar, digite *cancelar*.")]
        }
        GlobalCommand::Support => {
            if cfg.support_url.starts_with("https://") || cfg.support_url.starts_with("http://") {
                vec![text(format!("Canal de atendimento: {}", cfg.support_url))]
            } else {
                vec![text("O canal de atendimento humano ainda não está configurado. Não envie dados sensíveis por aqui.")]
            }
        }
    };
    store(db, chat_id, session, messages).await
}

fn start_alert(cfg: &Config, session: &mut Session) -> Vec<OutMsg> {
    session.draft = Draft::default();
    if cfg.alert_nl_enabled {
        session.step = Step::Intent;
        vec![text(intent_prompt())]
    } else {
        session.step = Step::City;
        vec![text(city_prompt())]
    }
}

async fn on_menu(
    db: &Db,
    cfg: &Config,
    http: &reqwest::Client,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
    audio_seconds: Option<u32>,
    quota_preconsumed: bool,
) -> anyhow::Result<Vec<OutMsg>> {
    match raw.trim() {
        "1" => Ok(start_alert(cfg, session)),
        "2" => list_alerts(db, chat_id, session).await,
        "3" => {
            session.step = Step::Menu;
            Ok(vec![text(help_text()), menu_message()])
        }
        // Fora do menu desde a simplificação; seguem aceitos por número para
        // quem já conhece o fluxo (ou estava no meio dele).
        "4" => list_watches(db, chat_id, session).await,
        "5" => start_email(db, cfg, chat_id, session).await,
        _ => {
            assistant_turn(
                db,
                cfg,
                http,
                chat_id,
                session,
                raw,
                audio_seconds,
                quota_preconsumed,
            )
            .await
        }
    }
}

async fn assistant_turn(
    db: &Db,
    cfg: &Config,
    http: &reqwest::Client,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
    audio_seconds: Option<u32>,
    quota_preconsumed: bool,
) -> anyhow::Result<Vec<OutMsg>> {
    let now = Utc::now().timestamp();
    if session
        .assistant_history_updated_at
        .is_some_and(|updated| now - updated > cfg.assistant_memory_ttl_seconds)
    {
        session.assistant_history.clear();
    }
    let messages = if cfg.llm_provider == "openai" && !cfg.openai_api_key.is_empty() {
        let allowed = if quota_preconsumed {
            true
        } else {
            db.consume_assistant_usage(chat_id, audio_seconds, cfg)
                .await?
        };
        if !allowed {
            let user = db.get_user(chat_id).await?;
            let pro = Db::is_pro(user.as_ref(), Utc::now());
            let limit = if audio_seconds.is_some() {
                if pro {
                    cfg.assistant_pro_audio_per_day
                } else {
                    cfg.assistant_free_audio_per_day
                }
            } else if pro {
                cfg.assistant_pro_messages_per_day
            } else {
                cfg.assistant_free_messages_per_day
            };
            let item = if audio_seconds.is_some() {
                "áudios"
            } else {
                "mensagens do assistente"
            };
            vec![text(format!(
                "Você atingiu o limite diário de {limit} {item} do {}. Tente novamente amanhã.",
                if pro { "Radar Pro" } else { "plano grátis" }
            ))]
        } else {
            let history_start = session
                .assistant_history
                .len()
                .saturating_sub(cfg.assistant_memory_turns.saturating_mul(2));
            let history = session.assistant_history[history_start..].to_vec();
            let state = draft_state(&session.draft);
            match call_assistant_function(http, cfg, raw, &history, state.as_deref()).await {
                Ok(Some(call)) => {
                    if call.total_tokens.is_some() {
                        let input_tokens = call.input_tokens.unwrap_or_default();
                        let output_tokens = call.output_tokens.unwrap_or_default();
                        match db
                            .record_assistant_tokens(chat_id, input_tokens, output_tokens)
                            .await
                        {
                            Ok(total) if total >= cfg.assistant_daily_token_alert as u64 => {
                                tracing::warn!(
                                    daily_tokens = total,
                                    "limite de custo de modelo atingido"
                                );
                            }
                            Ok(_) => {}
                            Err(error) => {
                                tracing::error!(%error, "telemetria de tokens indisponível")
                            }
                        }
                    }
                    execute_assistant_call(db, chat_id, session, raw, &call).await?
                }
                Ok(None) | Err(_) => deterministic_assistant(db, chat_id, session, raw).await?,
            }
        }
    } else {
        deterministic_assistant(db, chat_id, session, raw).await?
    };
    let answer = messages
        .iter()
        .filter_map(|message| match message {
            OutMsg::Text(body) => Some(body.as_str()),
            OutMsg::Image { caption, .. } => Some(caption.as_str()),
            OutMsg::Buttons { body, .. } => Some(body.as_str()),
        })
        .collect::<Vec<_>>()
        .join("\n");
    remember_exchange(cfg, session, raw, &answer);
    Ok(messages)
}

async fn execute_assistant_call(
    db: &Db,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
    call: &AssistantFunctionCall,
) -> anyhow::Result<Vec<OutMsg>> {
    tracing::info!(tool = %call.name, total_tokens = ?call.total_tokens, "assistant function call");
    let args = &call.arguments;
    match call.name.as_str() {
        "list_alerts" => list_alerts(db, chat_id, session).await,
        "create_alert" => apply_assistant_create(db, session, args, raw).await,
        "remove_alerts" => {
            let reference = args["alert_ref"].as_str().unwrap_or("");
            start_assistant_remove(db, chat_id, session, reference).await
        }
        "consult_market" => assistant_market(db, args).await,
        "help" => Ok(vec![text(help_text())]),
        "respond" => {
            let answer = args["text"]
                .as_str()
                .unwrap_or("Posso ajudar com alertas e dados do mercado imobiliário.");
            Ok(vec![text(answer.chars().take(800).collect::<String>())])
        }
        _ => {
            session.step = Step::Menu;
            Ok(vec![
                text("Posso ajudar com alertas imobiliários nas cidades cobertas."),
                menu_message(),
            ])
        }
    }
}

async fn deterministic_assistant(
    db: &Db,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
) -> anyhow::Result<Vec<OutMsg>> {
    let norm = normalize_text(raw);
    if [
        "meus alertas",
        "quais sao meus alertas",
        "listar alertas",
        "alertas",
    ]
    .iter()
    .any(|pattern| norm.contains(pattern))
    {
        return list_alerts(db, chat_id, session).await;
    }
    if ["remover", "apagar alerta", "excluir alerta", "apaga alerta"]
        .iter()
        .any(|pattern| norm.contains(pattern))
    {
        let reference = raw
            .split_once("alerta")
            .map(|(_, rest)| {
                rest.trim_matches(|ch: char| ch.is_ascii_punctuation() || ch.is_whitespace())
            })
            .unwrap_or("");
        return start_assistant_remove(db, chat_id, session, reference).await;
    }
    if [
        "media",
        "média",
        "preco",
        "preço",
        "mercado",
        "por m2",
        "por metro quadrado",
    ]
    .iter()
    .any(|pattern| norm.contains(pattern))
    {
        let extracted = mock_extract_alert(raw);
        let args = json!({
            "municipality": extracted.municipality,
            "listing_kind": extracted.listing_kind,
            "neighbourhoods": extracted.neighbourhoods,
            "metric": if norm.contains("m2") || norm.contains("metro quadrado") { "mean_price_m2" } else { "mean_price" }
        });
        return assistant_market(db, &args).await;
    }
    if [
        "ajuda",
        "help",
        "o que voce faz",
        "comandos",
        "como funciona",
    ]
    .iter()
    .any(|pattern| norm.contains(pattern))
    {
        session.step = Step::Menu;
        return Ok(vec![text(help_text())]);
    }
    if [
        "quero",
        "procuro",
        "criar alerta",
        "novo alerta",
        "apartamento",
        "apto",
        "alugar",
        "comprar",
    ]
    .iter()
    .any(|pattern| norm.contains(pattern))
    {
        let extracted = mock_extract_alert(raw);
        let args = json!({
            "municipality": extracted.municipality,
            "listing_kind": extracted.listing_kind,
            "categories": extracted.categories,
            "min_price": extracted.min_price,
            "max_price": extracted.max_price,
            "min_rooms": extracted.min_rooms,
            "neighbourhoods": extracted.neighbourhoods,
            "alert_name": null
        });
        return apply_assistant_create(db, session, &args, raw).await;
    }
    session.step = Step::Menu;
    Ok(vec![text("Posso ajudar a criar, listar ou remover alertas e consultar o mercado em Maceió, Recife e Natal.")])
}

async fn apply_assistant_create(
    db: &Db,
    session: &mut Session,
    args: &Value,
    raw: &str,
) -> anyhow::Result<Vec<OutMsg>> {
    let extracted = mock_extract_alert(raw);
    if let Some(city) = args["municipality"]
        .as_str()
        .or(extracted.municipality.as_deref())
    {
        if !matches!(city, "Maceió" | "Recife" | "Natal") {
            session.step = Step::AssistantConversation;
            return Ok(vec![text(
                "Ainda não cobrimos essa cidade. Hoje atendemos Maceió, Recife e Natal.",
            )]);
        }
        session.draft.municipality = Some(city.to_string());
    }
    if let Some(kind) = args["listing_kind"]
        .as_str()
        .or(extracted.listing_kind.as_deref())
    {
        if matches!(kind, "aluguel" | "venda") {
            session.draft.listing_kind = Some(kind.to_string());
        }
    }
    let minimum = args["min_price"].as_i64().or(extracted.min_price);
    let maximum = args["max_price"].as_i64().or(extracted.max_price);
    if minimum.is_some_and(|value| value <= 0) || maximum.is_some_and(|value| value <= 0) {
        session.step = Step::AssistantConversation;
        return Ok(vec![text(
            "O preço precisa ser maior que zero. Qual faixa você procura?",
        )]);
    }
    if minimum.zip(maximum).is_some_and(|(min, max)| min > max) {
        session.step = Step::AssistantConversation;
        return Ok(vec![text(
            "O preço mínimo ficou acima do máximo. Qual faixa devo usar?",
        )]);
    }
    if minimum.is_some() {
        session.draft.min_price = minimum;
    }
    if maximum.is_some() {
        session.draft.max_price = maximum;
    }
    if let Some(rooms) = args["min_rooms"]
        .as_i64()
        .or(extracted.min_rooms.map(i64::from))
    {
        if (1..=20).contains(&rooms) {
            session.draft.min_rooms = Some(rooms as i32);
        }
    }
    if let Some(categories) = args["categories"].as_array() {
        session.draft.categories = categories
            .iter()
            .filter_map(Value::as_str)
            .filter(|value| matches!(*value, "Apartamentos" | "Casas" | "Aluguel de quartos"))
            .map(str::to_string)
            .collect();
    } else if let Some(categories) = extracted.categories {
        session.draft.categories = categories;
    }

    let has_any_neighbourhood = raw.to_lowercase().contains("qualquer bairro")
        || raw.to_lowercase().contains("todos os bairros");
    let raw_neighbourhoods: Vec<String> = args["neighbourhoods"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(str::to_string)
        .collect();
    let raw_neighbourhoods = if raw_neighbourhoods.is_empty() {
        extracted.neighbourhoods.unwrap_or_default()
    } else {
        raw_neighbourhoods
    };
    if has_any_neighbourhood {
        session.draft.neighbourhoods.clear();
        session.draft.pending_raw_neighbourhoods.clear();
    } else if !raw_neighbourhoods.is_empty() {
        let Some(city) = session.draft.municipality.clone() else {
            session.draft.pending_raw_neighbourhoods = raw_neighbourhoods;
            session.step = Step::AssistantConversation;
            return Ok(vec![text(
                "Qual cidade? Hoje atendemos Maceió, Recife e Natal.",
            )]);
        };
        apply_neighbourhoods(db, session, &raw_neighbourhoods).await?;
        if session.draft.neighbourhoods.is_empty() {
            session.draft.pending_raw_neighbourhoods = raw_neighbourhoods.clone();
            session.step = Step::AssistantConversation;
            // Sem sugestão a conversa fica sem saída: a pessoa repete o nome
            // correto e recebe a mesma negativa, o que parece amnésia.
            let available = db
                .neighbourhoods(&city, session.draft.listing_kind.as_deref())
                .await
                .unwrap_or_default();
            let mut guessed: Vec<String> = Vec::new();
            for name in &raw_neighbourhoods {
                for candidate in closest_neighbourhoods(name, &available, 3) {
                    if !guessed.contains(&candidate) {
                        guessed.push(candidate);
                    }
                }
            }
            guessed.truncate(3);
            return Ok(vec![text(if guessed.is_empty() {
                format!(
                    "Não localizei esse bairro em {city}. Quer tentar outro ou usar qualquer bairro?"
                )
            } else {
                format!(
                    "Não localizei esse bairro em {city}. Temos estes parecidos: {}. Responda com o nome ou diga *qualquer bairro*.",
                    guessed.join(", ")
                )
            })]);
        }
    }

    let price_reference = session.draft.max_price.or(session.draft.min_price);
    if session.draft.listing_kind.is_none() {
        if let Some(price) = price_reference {
            if price <= 20_000 {
                session.draft.listing_kind = Some("aluguel".to_string());
            } else if price >= 50_000 {
                session.draft.listing_kind = Some("venda".to_string());
            }
        }
    }
    let mut missing = Vec::new();
    if session.draft.municipality.is_none() {
        missing.push("a cidade (Maceió, Recife ou Natal)".to_string());
    }
    if session.draft.listing_kind.is_none() {
        missing.push("o tipo: aluguel ou venda".to_string());
    }
    if session.draft.min_price.is_none() && session.draft.max_price.is_none() {
        missing.push("a faixa de preço".to_string());
    }
    if !missing.is_empty() {
        session.step = Step::AssistantConversation;
        return Ok(vec![text(format!(
            "Para montar seu alerta, me diga {}.",
            missing.join(" e ")
        ))]);
    }
    let suggested_name = auto_alert_name(&session.draft);
    let name = args["alert_name"]
        .as_str()
        .filter(|value| !value.trim().is_empty())
        .map(|value| value.chars().take(120).collect())
        .unwrap_or(suggested_name);
    session.draft.alert_name = Some(name);
    session.step = Step::Confirm;
    Ok(vec![confirm_message(&session.draft)])
}

async fn start_assistant_remove(
    db: &Db,
    chat_id: i64,
    session: &mut Session,
    reference: &str,
) -> anyhow::Result<Vec<OutMsg>> {
    let alerts = db.alerts_for_user(chat_id).await?;
    if alerts.is_empty() {
        session.step = Step::Menu;
        return Ok(vec![text("Você ainda não tem alertas para remover.")]);
    }
    let reference = normalize_text(reference);
    let candidates: Vec<_> = alerts
        .iter()
        .filter(|alert| {
            reference.is_empty()
                || normalize_text(&format!(
                    "{} {} {} {}",
                    alert.alert_name.as_deref().unwrap_or(""),
                    alert.municipality,
                    alert.neighbourhoods.join(" "),
                    alert.listing_kind
                ))
                .contains(&reference)
        })
        .collect();
    if candidates.is_empty() {
        session.step = Step::Menu;
        return Ok(vec![text(
            "Não encontrei esse alerta. Digite *meus alertas* para ver os seus.",
        )]);
    }
    if candidates.len() == 1 {
        let alert = candidates[0];
        session.step = Step::AssistantDeleteConfirm { id: alert.id };
        return Ok(vec![confirm_removal_message(alert)]);
    }
    let ids: Vec<i32> = candidates.iter().map(|alert| alert.id).collect();
    session.step = Step::AssistantRemoveChoice { ids };
    let mut lines = vec!["Encontrei mais de um alerta. Qual você quer remover?".to_string()];
    for (index, alert) in candidates.iter().enumerate() {
        lines.push(format!(
            "{}. {} · {} · {}",
            index + 1,
            alert.alert_name.as_deref().unwrap_or("Sem nome"),
            alert.municipality,
            alert.neighbourhoods.join(", ")
        ));
    }
    lines.push("Responda com o número. Não vou remover vários alertas de uma vez.".to_string());
    let choices = candidates
        .iter()
        .take(interactive::MAX_BUTTONS)
        .enumerate()
        .map(|(index, alert)| {
            button(
                &(index + 1).to_string(),
                &button_label(alert.alert_name.as_deref().unwrap_or("Sem nome")),
            )
        })
        .collect();
    Ok(vec![buttons(lines.join("\n"), choices)])
}

async fn assistant_market(db: &Db, args: &Value) -> anyhow::Result<Vec<OutMsg>> {
    let Some(municipality) = args["municipality"].as_str() else {
        return Ok(vec![text(
            "De qual cidade você quer consultar: Maceió, Recife ou Natal?",
        )]);
    };
    if !matches!(municipality, "Maceió" | "Recife" | "Natal") {
        return Ok(vec![text(
            "Ainda não cobrimos essa cidade. Hoje atendemos Maceió, Recife e Natal.",
        )]);
    }
    let Some(kind) = args["listing_kind"].as_str() else {
        return Ok(vec![text("Você quer consultar aluguel ou venda?")]);
    };
    if !matches!(kind, "aluguel" | "venda") {
        return Ok(vec![text("Você quer consultar aluguel ou venda?")]);
    }
    let Some(snapshot) = db.snapshot().await? else {
        return Ok(vec![text(
            "A coleta de mercado ainda não está disponível. Tente novamente mais tarde.",
        )]);
    };
    let Some(city) = snapshot["cities"].as_array().and_then(|cities| {
        cities
            .iter()
            .find(|city| city["municipality"] == municipality)
    }) else {
        return Ok(vec![text(format!(
            "Ainda não há dados de mercado de {municipality}."
        ))]);
    };
    let Some(stats) = city["kinds"].get(kind) else {
        return Ok(vec![text(format!(
            "Ainda não há amostra de {kind} em {municipality}."
        ))]);
    };
    let metric = args["metric"].as_str().unwrap_or("mean_price");
    let field = if metric == "mean_price_m2" {
        "mean_price_m2"
    } else {
        "mean_price"
    };
    let raw_neighbourhoods: Vec<String> = args["neighbourhoods"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(str::to_string)
        .collect();
    let row: Option<Value> = if raw_neighbourhoods.is_empty() {
        None
    } else {
        let rows = stats["neighbourhoods"]
            .as_array()
            .cloned()
            .unwrap_or_default();
        let available: Vec<String> = rows
            .iter()
            .filter_map(|row| row["name"].as_str().map(str::to_string))
            .collect();
        let matched = match_neighbourhoods(Some(&raw_neighbourhoods), &available);
        matched.first().and_then(|name| {
            rows.iter()
                .find(|row| row["name"].as_str() == Some(name.as_str()))
                .cloned()
        })
    };
    let is_neighbourhood = row.is_some();
    let source = row.as_ref().unwrap_or(stats);
    if is_neighbourhood && source["ranked"].as_bool() != Some(true) {
        return Ok(vec![text("Ainda não há amostra confiável desse bairro.")]);
    }
    let Some(value) = source[field].as_i64() else {
        return Ok(vec![text(
            "Ainda não há essa métrica na coleta mais recente.",
        )]);
    };
    let label = if field == "mean_price_m2" {
        "Preço médio pedido por m²"
    } else {
        "Média do preço pedido"
    };
    let location = row
        .as_ref()
        .and_then(|row| row["name"].as_str())
        .map(|name| format!("em {name}, {municipality}"))
        .unwrap_or_else(|| format!("em {municipality}"));
    let sample = source["sample"]
        .as_i64()
        .map(|count| format!(" · {count} anúncios na amostra"))
        .unwrap_or_default();
    let per_m2 = if field == "mean_price_m2" { "/m²" } else { "" };
    Ok(vec![text(format!(
        "{label} de {kind} {location}: *{}*{per_m2}{sample}.\n\nPreço pedido no OLX; valor pode mudar e a negociação é com o anunciante.",
        format_brl(Some(value))
    ))])
}

/// Oferta do Pro pago: dois planos, Pix ou cartão.
///
/// Sem `MP_ACCESS_TOKEN` cai no texto antigo (trial por e-mail), então ligar a
/// cobrança é só configurar as credenciais — o comportamento de hoje não muda
/// enquanto isso.
async fn on_assinatura(
    db: &Db,
    cfg: &Config,
    http: &reqwest::Client,
    chat_id: i64,
    session: &mut Session,
) -> anyhow::Result<Vec<OutMsg>> {
    let user = db.get_user(chat_id).await.ok().flatten();
    if Db::is_pro(user.as_ref(), Utc::now()) {
        session.step = Step::Menu;
        let until = user
            .as_ref()
            .and_then(|user| user.pro_until)
            .map(|until| until.format("%d/%m/%Y").to_string())
            .unwrap_or_else(|| "—".to_string());
        return Ok(vec![
            text(format!("✅ *Radar Pro ativo* até {until}.")),
            menu_message(),
        ]);
    }
    let mp = pagamentos::MercadoPago::from_config(cfg, http.clone());
    if !mp.habilitado() {
        session.step = Step::Menu;
        return Ok(vec![text(pro_pitch(cfg)), menu_message()]);
    }
    session.step = Step::Assinar;
    let precos = pagamentos::PrecosPlanos::da_config(cfg);
    let choices = pagamentos::planos(precos)
        .iter()
        .map(|plano| button(plano.id, &button_label(plano.titulo)))
        .collect();
    Ok(vec![buttons(planos_prompt(cfg), choices)])
}

/// Depois de escolhido o plano: cria a cobrança, gera o link e manda.
async fn on_assinar_plano(
    db: &Db,
    cfg: &Config,
    http: &reqwest::Client,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
) -> anyhow::Result<Vec<OutMsg>> {
    let precos = pagamentos::PrecosPlanos::da_config(cfg);
    let Some(plano) = pagamentos::plano_por_id(precos, raw) else {
        session.step = Step::Assinar;
        return Ok(vec![text(
            "Responda *1* para o plano de 1 mês ou *2* para o de 6 meses.",
        )]);
    };
    let mp = pagamentos::MercadoPago::from_config(cfg, http.clone());
    if !mp.habilitado() {
        session.step = Step::Menu;
        return Ok(vec![text(pro_pitch(cfg)), menu_message()]);
    }
    let referencia = pagamentos::nova_referencia(chat_id, &pagamentos::token_aleatorio());
    db.criar_pagamento(chat_id, &referencia, plano.valor_centavos, plano.dias)
        .await?;
    match mp
        .criar_preferencia(&referencia, plano.valor_centavos, plano.dias, plano.titulo)
        .await
    {
        Ok(link) => {
            session.step = Step::Menu;
            Ok(vec![
                text(pagamento_link(&link, plano.titulo, plano.valor_centavos)),
                text("Assim que o pagamento entrar, o Pro liga sozinho e eu te aviso. Se liberar e nada acontecer, responda *já paguei*."),
            ])
        }
        Err(error) => {
            tracing::error!(%error, "criar preferência de pagamento");
            session.step = Step::Menu;
            Ok(vec![
                text("Não consegui gerar o link de pagamento agora. Tente novamente em instantes."),
                menu_message(),
            ])
        }
    }
}

/// "Já paguei": reconfere na API em vez de mandar pagar de novo.
async fn on_ja_paguei(
    db: &Db,
    cfg: &Config,
    http: &reqwest::Client,
    chat_id: i64,
    session: &mut Session,
) -> anyhow::Result<Vec<OutMsg>> {
    let mp = pagamentos::MercadoPago::from_config(cfg, http.clone());
    if !mp.habilitado() {
        session.step = Step::Menu;
        return Ok(vec![text(pro_pitch(cfg)), menu_message()]);
    }
    let Some(pendente) = db.pagamento_pendente(chat_id).await? else {
        session.step = Step::Menu;
        return Ok(vec![
            text("Não encontrei uma cobrança em aberto nesta conversa. Responda *pro* para ver os planos."),
            menu_message(),
        ]);
    };
    session.step = Step::Menu;
    let mensagem = match pagamentos::processar_referencia(db, &mp, &pendente.referencia).await {
        Ok(pagamentos::ResultadoPagamento::Ativado { dias }) => {
            format!("✅ Pagamento confirmado! *Radar Pro* ativo por {dias} dias.")
        }
        Ok(pagamentos::ResultadoPagamento::JaContabilizado) => {
            "✅ Esse pagamento já estava contabilizado; seu Pro segue ativo.".to_string()
        }
        Ok(pagamentos::ResultadoPagamento::Recusado) => {
            "O pagamento encontrado não confere com a cobrança desta conversa. Vou encaminhar ao suporte humano.".to_string()
        }
        Ok(_) => {
            "Ainda não vejo o pagamento confirmado. Pix e boleto podem levar alguns minutos; se você pagou agora, tente de novo em instantes.".to_string()
        }
        Err(error) => {
            tracing::error!(%error, "reconferir pagamento");
            "Não consegui consultar o pagamento agora. Tente novamente em instantes.".to_string()
        }
    };
    Ok(vec![text(mensagem), menu_message()])
}

async fn on_assistant_remove_choice(
    db: &Db,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
    ids: &[i32],
) -> anyhow::Result<Vec<OutMsg>> {
    let Ok(index) = raw.trim().parse::<usize>() else {
        return Ok(vec![text(
            "Responda com o número do alerta que deseja remover.",
        )]);
    };
    let Some(id) = ids.get(index.saturating_sub(1)).copied() else {
        return Ok(vec![text(
            "Esse número não está na lista. Escolha um alerta da lista.",
        )]);
    };
    let Some(alert) = db.alert_for_user(chat_id, id).await? else {
        session.step = Step::Menu;
        return Ok(vec![text(
            "Não encontrei esse alerta. Digite *meus alertas* para atualizar a lista.",
        )]);
    };
    session.step = Step::AssistantDeleteConfirm { id };
    Ok(vec![confirm_removal_message(&alert)])
}

async fn on_assistant_delete_confirm(
    db: &Db,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
    id: i32,
) -> anyhow::Result<Vec<OutMsg>> {
    match normalize_text(raw).as_str() {
        "1" | "sim" | "confirmar" | "confirmar remocao" | "remover" => {
            let deleted = db.delete_alert(chat_id, id).await?;
            session.step = Step::Menu;
            let result = if deleted {
                "Alerta removido."
            } else {
                "Não encontrei esse alerta."
            };
            Ok(vec![text(result), menu_message()])
        }
        "2" | "nao" | "cancelar" | "cancela" => {
            session.step = Step::Menu;
            Ok(vec![text("Tudo bem, não removi o alerta."), menu_message()])
        }
        _ => Ok(vec![text(
            "Responda *1* para confirmar a remoção ou *2* para cancelar.",
        )]),
    }
}

async fn on_delete_account_confirm(
    db: &Db,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
) -> anyhow::Result<Vec<OutMsg>> {
    if normalize_text(raw) == "excluir" {
        match db.delete_whatsapp_user_data(chat_id).await {
            Ok(true) => {
                *session = Session::menu();
                session.step = Step::Deleted;
                Ok(vec![text("Seus dados do André Assistente Imobiliário foram excluídos. As mensagens enviadas continuam no histórico do WhatsApp.")])
            }
            Ok(false) => {
                session.step = Step::Deleted;
                Ok(vec![text("Não encontrei uma conta WhatsApp para excluir.")])
            }
            Err(error) => {
                tracing::error!(%error, "exclusão de dados WhatsApp");
                session.step = Step::DeleteAccountConfirm;
                Ok(vec![text("Não consegui concluir a exclusão agora. Tente novamente ou fale com o suporte.")])
            }
        }
    } else if matches!(normalize_text(raw).as_str(), "cancelar" | "nao" | "não") {
        *session = Session::menu();
        Ok(vec![
            text("Solicitação cancelada; seus dados foram mantidos."),
            menu_message(),
        ])
    } else {
        Ok(vec![text(
            "Para confirmar a exclusão, responda *EXCLUIR*. Para cancelar, digite *cancelar*.",
        )])
    }
}

fn remember_exchange(cfg: &Config, session: &mut Session, user: &str, assistant: &str) {
    let clean = |value: &str| -> String {
        let email = regex::Regex::new(r"(?i)[\w.+-]+@[\w.-]+\.[a-z]{2,}").unwrap();
        let document = regex::Regex::new(r"\b(?:\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})\b").unwrap();
        let card = regex::Regex::new(r"\b(?:\d[ -]?){13,19}\b").unwrap();
        let value = email.replace_all(value, "[e-mail removido]");
        let value = document.replace_all(&value, "[documento removido]");
        card.replace_all(&value, "[número removido]")
            .chars()
            .take(1600)
            .collect()
    };
    session
        .assistant_history
        .push(json!({"role":"user","content":clean(user)}));
    session
        .assistant_history
        .push(json!({"role":"assistant","content":clean(assistant)}));
    let max_entries = cfg.assistant_memory_turns.saturating_mul(2);
    if session.assistant_history.len() > max_entries {
        let remove = session.assistant_history.len() - max_entries;
        session.assistant_history.drain(0..remove);
    }
    session.assistant_history_updated_at = Some(Utc::now().timestamp());
}

async fn on_intent(
    db: &Db,
    cfg: &Config,
    http: &reqwest::Client,
    _chat_id: i64,
    session: &mut Session,
    raw: &str,
) -> anyhow::Result<Vec<OutMsg>> {
    let norm = normalize_text(raw);
    if norm == "1" || norm == "botoes" || norm == "passo a passo" {
        session.draft = Draft::default();
        session.step = Step::City;
        return Ok(vec![text(city_prompt())]);
    }
    let Some(extracted) = extract_alert_intent(http, cfg, raw).await else {
        return Ok(vec![text(
            "Manda uma frase sobre o imóvel, ou *1* para o passo a passo.",
        )]);
    };
    session.draft.nl_mode = true;
    if matches!(
        extracted.municipality.as_deref(),
        Some("Maceió" | "Recife" | "Natal")
    ) {
        session.draft.municipality = extracted.municipality;
    }
    if matches!(extracted.listing_kind.as_deref(), Some("aluguel" | "venda")) {
        session.draft.listing_kind = extracted.listing_kind;
    }
    if let Some(categories) = extracted.categories {
        let valid: Vec<String> = categories
            .into_iter()
            .filter(|category| {
                matches!(
                    category.as_str(),
                    "Apartamentos" | "Casas" | "Aluguel de quartos"
                )
            })
            .collect();
        if !valid.is_empty() {
            session.draft.categories = valid;
        }
    }
    if extracted.min_price.unwrap_or(0) > 0 {
        session.draft.min_price = extracted.min_price;
    }
    if extracted.max_price.unwrap_or(0) > 0 {
        session.draft.max_price = extracted.max_price;
    }
    if extracted.min_rooms.unwrap_or(0) > 0 {
        session.draft.min_rooms = extracted.min_rooms;
    }
    if let Some(raw_neighbourhoods) = extracted.neighbourhoods {
        if session.draft.municipality.is_some() {
            apply_neighbourhoods(db, session, &raw_neighbourhoods).await?;
        } else {
            session.draft.pending_raw_neighbourhoods = raw_neighbourhoods;
        }
    }
    Ok(advance_nl(session))
}

fn advance_nl(session: &mut Session) -> Vec<OutMsg> {
    if session.draft.municipality.is_none() {
        session.step = Step::City;
        return vec![text(
            "📍 *Em qual cidade você procura?*\n1. Maceió\n2. Recife\n3. Natal",
        )];
    }
    if session.draft.listing_kind.is_none() {
        session.step = Step::Kind;
        return vec![text(kind_prompt())];
    }
    if session.draft.min_price.is_none() && session.draft.max_price.is_none() {
        session.step = Step::Price;
        return vec![text(price_prompt(
            session.draft.listing_kind.as_deref().unwrap_or("aluguel"),
            session.draft.municipality.as_deref().unwrap_or("Maceió"),
        ))];
    }
    if session.draft.alert_name.is_none() {
        session.draft.alert_name = Some(auto_alert_name(&session.draft));
    }
    session.step = Step::Confirm;
    vec![confirm_message(&session.draft)]
}

async fn apply_neighbourhoods(
    db: &Db,
    session: &mut Session,
    raw: &[String],
) -> anyhow::Result<()> {
    let city = session
        .draft
        .municipality
        .clone()
        .unwrap_or_else(|| "Maceió".into());
    let available = db
        .neighbourhoods(&city, session.draft.listing_kind.as_deref())
        .await
        .unwrap_or_default();
    session.draft.neighbourhoods = match_neighbourhoods(Some(raw), &available);
    session.draft.pending_raw_neighbourhoods.clear();
    Ok(())
}

async fn on_city(db: &Db, session: &mut Session, raw: &str) -> anyhow::Result<Vec<OutMsg>> {
    let norm = normalize_text(raw);
    let city = match raw.trim() {
        "1" => "Maceió",
        "2" => "Recife",
        "3" => "Natal",
        _ if norm.contains("maceio") => "Maceió",
        _ if norm.contains("recife") => "Recife",
        _ if norm.contains("natal") => "Natal",
        _ => return Ok(vec![text("Responda 1, 2 ou 3."), text(city_prompt())]),
    };
    session.draft.municipality = Some(city.to_string());
    session.draft.neighbourhoods.clear();
    let pending = session.draft.pending_raw_neighbourhoods.clone();
    if !pending.is_empty() {
        apply_neighbourhoods(db, session, &pending).await?;
    }
    if session.draft.nl_mode {
        return Ok(advance_nl(session));
    }
    session.step = Step::Kind;
    Ok(vec![
        text(format!("📍 *Cidade:* {city}")),
        text(kind_prompt()),
    ])
}

fn on_kind(session: &mut Session, raw: &str) -> Vec<OutMsg> {
    let norm = normalize_text(raw);
    let kind = match raw.trim() {
        "1" => "aluguel",
        "2" => "venda",
        _ if norm.contains("aluga") || norm.contains("aluguel") || norm.contains("mensal") => {
            "aluguel"
        }
        _ if norm.contains("vend") || norm.contains("compr") || norm.contains("propriet") => {
            "venda"
        }
        _ => {
            return vec![
                text("Responda 1 para alugar ou 2 para comprar."),
                text(kind_prompt()),
            ]
        }
    };
    session.draft.listing_kind = Some(kind.to_string());
    session.draft.categories.retain(|category| {
        category_options(kind)
            .iter()
            .any(|(value, _)| value == category)
    });
    if session.draft.nl_mode {
        return advance_nl(session);
    }
    session.step = Step::Categories;
    vec![text(categories_prompt(kind, &session.draft.categories))]
}

fn on_categories(session: &mut Session, raw: &str) -> Vec<OutMsg> {
    let kind = session.draft.listing_kind.as_deref().unwrap_or("aluguel");
    let options = category_options(kind);
    let norm = normalize_text(raw);
    if raw.trim() == "0" || norm == "ok" || norm == "concluir" || norm == "pronto" {
        if session.draft.nl_mode {
            return advance_nl(session);
        }
        session.step = Step::Price;
        return vec![text(price_prompt(
            kind,
            session.draft.municipality.as_deref().unwrap_or("Maceió"),
        ))];
    }
    let Some(indexes) = parse_index_list(raw) else {
        return vec![text(categories_prompt(kind, &session.draft.categories))];
    };
    for index in indexes {
        let Some((value, _)) = options.get(index - 1) else {
            return vec![
                text("Número fora da lista."),
                text(categories_prompt(kind, &session.draft.categories)),
            ];
        };
        if let Some(pos) = session
            .draft
            .categories
            .iter()
            .position(|item| item == value)
        {
            session.draft.categories.remove(pos);
        } else {
            session.draft.categories.push((*value).to_string());
        }
    }
    vec![text(categories_prompt(kind, &session.draft.categories))]
}

fn on_price(session: &mut Session, raw: &str) -> Vec<OutMsg> {
    let kind = session
        .draft
        .listing_kind
        .clone()
        .unwrap_or_else(|| "aluguel".into());
    let city = session
        .draft
        .municipality
        .clone()
        .unwrap_or_else(|| "Maceió".into());
    if raw.trim() == "5" || normalize_text(raw) == "personalizado" {
        session.step = Step::PriceMin;
        return vec![text(price_min_prompt())];
    }
    let presets = price_presets(&kind, &city);
    let Ok(index) = raw.trim().parse::<usize>() else {
        // Áudio/fala: interpretar um valor falado como teto de orçamento.
        if let Some(value) = parse_money(raw) {
            session.draft.max_price = Some(value);
            return after_price(session);
        }
        return vec![
            text("Escolha um número da lista."),
            text(price_prompt(&kind, &city)),
        ];
    };
    let Some(preset) = presets.get(index - 1) else {
        return vec![
            text("Escolha um número da lista."),
            text(price_prompt(&kind, &city)),
        ];
    };
    session.draft.min_price = Some(preset.min);
    session.draft.max_price = Some(preset.max);
    after_price(session)
}

fn on_price_min(session: &mut Session, raw: &str) -> Vec<OutMsg> {
    let Some(min_price) = parse_money(raw) else {
        return vec![
            text("Número inválido. Ex.: 150000"),
            text(price_min_prompt()),
        ];
    };
    session.draft.min_price = Some(min_price);
    session.step = Step::PriceMax;
    vec![text(price_max_prompt())]
}

fn on_price_max(session: &mut Session, raw: &str) -> Vec<OutMsg> {
    let Some(max_price) = parse_money(raw) else {
        return vec![text("Número inválido."), text(price_max_prompt())];
    };
    if session.draft.min_price.unwrap_or(0) > max_price {
        return vec![
            text("O preço máximo deve ser maior ou igual ao mínimo."),
            text(price_max_prompt()),
        ];
    }
    session.draft.max_price = Some(max_price);
    after_price(session)
}

fn after_price(session: &mut Session) -> Vec<OutMsg> {
    if session.draft.nl_mode {
        return advance_nl(session);
    }
    session.step = Step::Rooms;
    vec![text(rooms_prompt())]
}

async fn on_rooms(db: &Db, session: &mut Session, raw: &str) -> anyhow::Result<Vec<OutMsg>> {
    let norm = normalize_text(raw);
    let rooms = match raw.trim() {
        "1" => None,
        "2" => Some(1),
        "3" => Some(2),
        "4" => Some(3),
        "5" => Some(4),
        _ if matches!(
            norm.as_str(),
            "qualquer" | "nenhum" | "indiferente" | "tanto faz"
        ) =>
        {
            None
        }
        _ if parse_number_words(raw).is_some() => parse_number_words(raw).map(|value| value as i32),
        _ => return Ok(vec![text("Responda de 1 a 5."), text(rooms_prompt())]),
    };
    session.draft.min_rooms = rooms;
    let city = session
        .draft
        .municipality
        .clone()
        .unwrap_or_else(|| "Maceió".into());
    let all = db
        .neighbourhoods(&city, session.draft.listing_kind.as_deref())
        .await
        .unwrap_or_default();
    session.step = Step::Neighbourhoods { page: 0 };
    Ok(vec![text(neighbourhoods_prompt(
        &all,
        0,
        &session.draft.neighbourhoods,
    ))])
}

async fn on_neighbourhoods(
    db: &Db,
    session: &mut Session,
    raw: &str,
    page: usize,
) -> anyhow::Result<Vec<OutMsg>> {
    let city = session
        .draft
        .municipality
        .clone()
        .unwrap_or_else(|| "Maceió".into());
    let all = db
        .neighbourhoods(&city, session.draft.listing_kind.as_deref())
        .await
        .unwrap_or_default();
    const PAGE: usize = 8;
    let pages = all.len().div_ceil(PAGE).max(1);
    let mut page = page.min(pages - 1);
    let norm = normalize_text(raw);
    if norm == "mais" || norm == "proxima" || norm == "proximo" {
        page = (page + 1).min(pages - 1);
        session.step = Step::Neighbourhoods { page };
        return Ok(vec![text(neighbourhoods_prompt(
            &all,
            page,
            &session.draft.neighbourhoods,
        ))]);
    }
    if norm == "voltar" || norm == "anterior" {
        page = page.saturating_sub(1);
        session.step = Step::Neighbourhoods { page };
        return Ok(vec![text(neighbourhoods_prompt(
            &all,
            page,
            &session.draft.neighbourhoods,
        ))]);
    }
    if raw.trim() == "0" || norm == "ok" || norm == "concluir" || norm == "todos" {
        session.draft.alert_name = Some(auto_alert_name(&session.draft));
        session.step = Step::Name;
        return Ok(vec![text(name_prompt(
            session.draft.alert_name.as_deref().unwrap_or("Alerta"),
        ))]);
    }
    if all.is_empty() {
        return Ok(vec![text(neighbourhoods_prompt(
            &all,
            page,
            &session.draft.neighbourhoods,
        ))]);
    }
    let Some(indexes) = parse_index_list(raw) else {
        // Áudio/fala: buscar bairros pelo nome (pode vir mais de um).
        let norm = normalize_text(raw);
        if norm.is_empty()
            || matches!(
                norm.as_str(),
                "qualquer" | "todas" | "todos" | "nenhum" | "indiferente" | "tanto faz"
            )
        {
            session.draft.alert_name = Some(auto_alert_name(&session.draft));
            session.step = Step::Name;
            return Ok(vec![text(name_prompt(
                session.draft.alert_name.as_deref().unwrap_or("Alerta"),
            ))]);
        }
        let chunks: Vec<String> = raw
            .split(|ch: char| matches!(ch, ',' | ';' | '(' | ')'))
            .flat_map(|part| part.split(" e "))
            .flat_map(|part| part.split(" ou "))
            .map(str::trim)
            .filter(|part| !part.is_empty())
            .map(str::to_string)
            .collect();
        let matched = match_neighbourhoods(
            if chunks.is_empty() {
                None
            } else {
                Some(&chunks)
            },
            &all,
        );
        if matched.is_empty() {
            return Ok(vec![
                text("Não reconheci esse bairro. Escolha um número da lista ou fale o nome."),
                text(neighbourhoods_prompt(
                    &all,
                    page,
                    &session.draft.neighbourhoods,
                )),
            ]);
        }
        for name in matched {
            if let Some(pos) = session
                .draft
                .neighbourhoods
                .iter()
                .position(|item| item == &name)
            {
                session.draft.neighbourhoods.remove(pos);
            } else {
                session.draft.neighbourhoods.push(name);
            }
        }
        session.step = Step::Neighbourhoods { page };
        return Ok(vec![text(neighbourhoods_prompt(
            &all,
            page,
            &session.draft.neighbourhoods,
        ))]);
    };
    let start = page * PAGE;
    for index in indexes {
        let Some(name) = all.get(start + index - 1) else {
            return Ok(vec![
                text("Número fora desta página."),
                text(neighbourhoods_prompt(
                    &all,
                    page,
                    &session.draft.neighbourhoods,
                )),
            ]);
        };
        if let Some(pos) = session
            .draft
            .neighbourhoods
            .iter()
            .position(|item| item == name)
        {
            session.draft.neighbourhoods.remove(pos);
        } else {
            session.draft.neighbourhoods.push(name.clone());
        }
    }
    session.step = Step::Neighbourhoods { page };
    Ok(vec![text(neighbourhoods_prompt(
        &all,
        page,
        &session.draft.neighbourhoods,
    ))])
}

fn on_name(session: &mut Session, raw: &str) -> Vec<OutMsg> {
    let name = if raw.trim() == "1" || normalize_text(raw) == "um" {
        session
            .draft
            .alert_name
            .clone()
            .unwrap_or_else(|| auto_alert_name(&session.draft))
    } else {
        let cleaned = raw.trim();
        if cleaned.chars().count() < 2 {
            return vec![
                text("Nome inválido. Tente de novo."),
                text(name_prompt(&auto_alert_name(&session.draft))),
            ];
        }
        cleaned.chars().take(120).collect()
    };
    session.draft.alert_name = Some(name);
    session.step = Step::Confirm;
    vec![confirm_message(&session.draft)]
}

async fn finish_alert(
    db: &Db,
    cfg: &Config,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
) -> anyhow::Result<Vec<OutMsg>> {
    match raw.trim() {
        "2" => {
            *session = Session::menu();
            return Ok(vec![text("Ok! O alerta não foi salvo."), menu_message()]);
        }
        "1" => {}
        _ => {
            return Ok(vec![text(
                "Responda *1* para confirmar ou *2* para cancelar.",
            )])
        }
    }
    if session.draft.min_price.is_none() && session.draft.max_price.is_none() {
        session.step = Step::Price;
        return Ok(vec![
            text("Falta a faixa de preço."),
            text(price_prompt(
                session.draft.listing_kind.as_deref().unwrap_or("aluguel"),
                session.draft.municipality.as_deref().unwrap_or("Maceió"),
            )),
        ]);
    }
    let status = match db.create_alert(chat_id, &session.draft, cfg).await {
        Ok(status) => status,
        Err(error) => {
            tracing::error!(%error, "criar alerta");
            return Ok(vec![text(
                "Não consegui salvar seu alerta agora. Tente novamente em instantes.",
            )]);
        }
    };
    match status {
        CreateAlertStatus::CapReached => {
            let user = db.get_user(chat_id).await.ok().flatten();
            let pro = Db::is_pro(user.as_ref(), Utc::now());
            *session = Session::menu();
            Ok(vec![text(cap_alerts(cfg, pro)), menu_message()])
        }
        CreateAlertStatus::Created(_) | CreateAlertStatus::Reused(_) => {
            let created = matches!(status, CreateAlertStatus::Created(_));
            show_matches(db, chat_id, session, created).await
        }
    }
}

async fn show_matches(
    db: &Db,
    chat_id: i64,
    session: &mut Session,
    created: bool,
) -> anyhow::Result<Vec<OutMsg>> {
    let rows = db.unnotified(chat_id).await.unwrap_or_default();
    if rows.is_empty() {
        *session = Session::menu();
        let body = if created {
            "✅ Alerta criado! Vou te avisar quando aparecer algo novo."
        } else {
            "ℹ️ Você já tem um alerta com esses filtros. Nenhum imóvel novo desde a última vez."
        };
        return Ok(vec![text(body), menu_message()]);
    }
    let alerts = db.active_alerts(chat_id).await.unwrap_or_default();
    let snapshot = db.snapshot().await.ok().flatten();
    let ranked = prepare_match_carousel(&rows, &alerts, snapshot.as_ref(), Utc::now());
    let pairs: Vec<(i32, i32)> = rows
        .iter()
        .map(|row| (row.alert_id, row.listing.listing_id))
        .collect();
    if let Err(error) = db.mark_notified(&pairs).await {
        tracing::error!(%error, "marcar matches");
    }
    let ids: Vec<i32> = ranked.iter().map(|item| item.listing.listing_id).collect();
    session.draft = Draft::default();
    session.step = Step::MatchCarousel {
        index: 0,
        listing_ids: ids,
    };
    let intro = if created {
        "✅ Encontrei imóveis para o seu alerta."
    } else {
        "ℹ️ Esse alerta já existia. Estes são os imóveis ainda não enviados."
    };
    let mut messages = vec![text(intro)];
    if let Some(first) = ranked.first() {
        messages.extend(card_messages(
            &first.listing,
            0,
            ranked.len(),
            Some(&first.headline),
        ));
    }
    Ok(messages)
}

fn listing_message(
    listing: &Listing,
    index: usize,
    total: usize,
    headline: Option<&str>,
) -> OutMsg {
    let caption = card_caption(listing, index, total, headline);
    if let Some(url) = listing.images.iter().find(|url| url.starts_with("http")) {
        OutMsg::Image {
            url: url.clone(),
            caption,
        }
    } else {
        text(caption)
    }
}

/// Botões do card do carrossel.
///
/// O WhatsApp aceita no máximo três respostas rápidas, então as três do toque
/// são as que mais se usa (avançar, acompanhar, menu); "anterior" continua no
/// texto e vira botão quando é o único caminho que resta (último card).
fn card_buttons(index: usize, total: usize) -> Vec<Button> {
    let mut items = Vec::new();
    if index + 1 < total {
        items.push(button("1", "Próximo"));
    } else if index > 0 {
        items.push(button("2", "Anterior"));
    }
    items.push(button("3", "Acompanhar"));
    items.push(button("4", "Menu"));
    items
}

/// Foto do imóvel + os botões de navegação do card.
fn card_messages(
    listing: &Listing,
    index: usize,
    total: usize,
    headline: Option<&str>,
) -> Vec<OutMsg> {
    vec![
        listing_message(listing, index, total, headline),
        buttons(NAV_HINT.to_string(), card_buttons(index, total)),
    ]
}

async fn on_match_carousel(
    db: &Db,
    cfg: &Config,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
    index: usize,
    listing_ids: &[i32],
) -> anyhow::Result<Vec<OutMsg>> {
    if listing_ids.is_empty() {
        *session = Session::menu();
        return Ok(vec![menu_message()]);
    }
    let mut index = index.min(listing_ids.len() - 1);
    match nav_action(raw) {
        Nav::Next => {
            if index + 1 >= listing_ids.len() {
                return Ok(vec![text("Esse é o último.")]);
            }
            index += 1;
        }
        Nav::Prev => {
            if index == 0 {
                return Ok(vec![text("Esse é o primeiro.")]);
            }
            index -= 1;
        }
        Nav::Third => {
            let listing_id = listing_ids[index];
            return Ok(watch_reply(db, cfg, chat_id, listing_id).await);
        }
        Nav::Menu => {
            *session = Session::menu();
            return Ok(vec![menu_message()]);
        }
        Nav::Unknown => return Ok(vec![text(NAV_HINT)]),
    }
    session.step = Step::MatchCarousel {
        index,
        listing_ids: listing_ids.to_vec(),
    };
    let Some(listing) = db.listing(listing_ids[index]).await? else {
        return Ok(vec![text("Não achei esse anúncio.")]);
    };
    Ok(card_messages(&listing, index, listing_ids.len(), None))
}

async fn watch_reply(db: &Db, cfg: &Config, chat_id: i64, listing_id: i32) -> Vec<OutMsg> {
    match db.create_watch(chat_id, listing_id, cfg).await {
        Ok(WatchStatus::Created(_)) => vec![text(
            "Anúncio adicionado. Aviso se o preço mudar ou se sair do ar.",
        )],
        Ok(WatchStatus::Duplicate(_)) => vec![text("Você já acompanha esse anúncio.")],
        Ok(WatchStatus::CapReached) => {
            let user = db.get_user(chat_id).await.ok().flatten();
            let pro = Db::is_pro(user.as_ref(), Utc::now());
            vec![text(cap_watches(cfg, pro))]
        }
        Ok(WatchStatus::ListingMissing) => vec![text("Não achei esse anúncio.")],
        Err(error) => {
            tracing::error!(%error, "criar watch");
            vec![down()]
        }
    }
}

async fn list_alerts(db: &Db, chat_id: i64, session: &mut Session) -> anyhow::Result<Vec<OutMsg>> {
    let alerts = match db.alerts_for_user(chat_id).await {
        Ok(alerts) => alerts,
        Err(error) => {
            tracing::error!(%error, "listar alertas");
            return Ok(vec![down()]);
        }
    };
    session.step = Step::Alerts {
        ids: alerts.iter().map(|alert| alert.id).collect(),
    };
    if alerts.is_empty() {
        return Ok(vec![buttons(
            alerts_list(&alerts),
            vec![button("1", "Novo alerta"), button("2", "Menu")],
        )]);
    }
    // Só cabem três botões: com mais alertas na lista, o número digitado segue
    // sendo o único jeito de escolher (os rótulos seriam ambíguos).
    if alerts.len() <= interactive::MAX_BUTTONS {
        let choices = alerts
            .iter()
            .enumerate()
            .map(|(index, alert)| {
                button(
                    &(index + 1).to_string(),
                    &button_label(alert.alert_name.as_deref().unwrap_or("Sem nome")),
                )
            })
            .collect();
        return Ok(vec![buttons(alerts_list(&alerts), choices)]);
    }
    Ok(vec![text(alerts_list(&alerts))])
}

async fn on_alerts(
    db: &Db,
    cfg: &Config,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
    ids: &[i32],
) -> anyhow::Result<Vec<OutMsg>> {
    if ids.is_empty() && raw.trim() == "1" {
        return Ok(start_alert(cfg, session));
    }
    if ids.is_empty() {
        *session = Session::menu();
        return Ok(vec![menu_message()]);
    }
    let Ok(index) = raw.trim().parse::<usize>() else {
        return list_alerts(db, chat_id, session).await;
    };
    let Some(id) = ids.get(index - 1).copied() else {
        return list_alerts(db, chat_id, session).await;
    };
    let Some(alert) = db.alert_for_user(chat_id, id).await? else {
        return list_alerts(db, chat_id, session).await;
    };
    session.step = Step::AlertDetail { id };
    Ok(vec![alert_detail_message(&alert)])
}

async fn on_alert_detail(
    db: &Db,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
    id: i32,
) -> anyhow::Result<Vec<OutMsg>> {
    match raw.trim() {
        "1" => {
            let Some(alert) = db.alert_for_user(chat_id, id).await? else {
                return list_alerts(db, chat_id, session).await;
            };
            session.step = Step::AssistantDeleteConfirm { id };
            Ok(vec![confirm_removal_message(&alert)])
        }
        "2" => {
            let name = db
                .alert_for_user(chat_id, id)
                .await?
                .and_then(|alert| alert.alert_name)
                .unwrap_or_else(|| "Sem nome".into());
            Ok(vec![edit_stub_message(&name)])
        }
        "3" => list_alerts(db, chat_id, session).await,
        _ => Ok(vec![text("1 apagar · 2 editar · 3 voltar")]),
    }
}

async fn list_watches(db: &Db, chat_id: i64, session: &mut Session) -> anyhow::Result<Vec<OutMsg>> {
    let watches = match db.watches(chat_id).await {
        Ok(watches) => watches,
        Err(error) => {
            tracing::error!(%error, "listar watches");
            return Ok(vec![down()]);
        }
    };
    if watches.is_empty() {
        *session = Session::menu();
        return Ok(vec![
            text("Você ainda não acompanha nenhum anúncio. Abra um match e responda *3*."),
            menu_message(),
        ]);
    }
    let ids: Vec<i32> = watches.iter().map(|watch| watch.id).collect();
    session.step = Step::WatchCarousel {
        index: 0,
        watch_ids: ids,
    };
    let first = &watches[0];
    Ok(vec![watch_message(&first.listing, 0, watches.len())])
}

fn watch_message(listing: &Listing, index: usize, total: usize) -> OutMsg {
    let caption = watch_card_caption(listing, index, total);
    if let Some(url) = listing.images.iter().find(|url| url.starts_with("http")) {
        OutMsg::Image {
            url: url.clone(),
            caption,
        }
    } else {
        text(caption)
    }
}

async fn on_watch_carousel(
    db: &Db,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
    index: usize,
    watch_ids: &[i32],
) -> anyhow::Result<Vec<OutMsg>> {
    if watch_ids.is_empty() {
        *session = Session::menu();
        return Ok(vec![menu_message()]);
    }
    let mut index = index.min(watch_ids.len() - 1);
    match nav_action(raw) {
        Nav::Next => {
            if index + 1 >= watch_ids.len() {
                return Ok(vec![text("Esse é o último.")]);
            }
            index += 1;
        }
        Nav::Prev => {
            if index == 0 {
                return Ok(vec![text("Esse é o primeiro.")]);
            }
            index -= 1;
        }
        Nav::Third => {
            let removed = db
                .delete_watch(chat_id, watch_ids[index])
                .await
                .unwrap_or(false);
            let note = if removed {
                "Parei de acompanhar esse anúncio."
            } else {
                "Não achei esse acompanhamento."
            };
            return Ok({
                let mut messages = vec![text(note)];
                messages.extend(list_watches(db, chat_id, session).await?);
                messages
            });
        }
        Nav::Menu => {
            *session = Session::menu();
            return Ok(vec![menu_message()]);
        }
        Nav::Unknown => return Ok(vec![text("1 próximo · 2 anterior · 3 parar · 4 menu")]),
    }
    session.step = Step::WatchCarousel {
        index,
        watch_ids: watch_ids.to_vec(),
    };
    let watches = db.watches(chat_id).await?;
    let Some(watch) = watches
        .into_iter()
        .find(|watch| watch.id == watch_ids[index])
    else {
        return list_watches(db, chat_id, session).await;
    };
    Ok(vec![watch_message(&watch.listing, index, watch_ids.len())])
}

async fn start_email(
    db: &Db,
    cfg: &Config,
    chat_id: i64,
    session: &mut Session,
) -> anyhow::Result<Vec<OutMsg>> {
    let user = db.get_user(chat_id).await.ok().flatten();
    if Db::is_pro(user.as_ref(), Utc::now()) {
        session.step = Step::Menu;
        return Ok(vec![
            text("✅ Você já tem o *Radar Pro* ativo."),
            menu_message(),
        ]);
    }
    session.step = Step::Email;
    Ok(vec![text(pro_pitch(cfg))])
}

async fn on_email(
    db: &Db,
    cfg: &Config,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
) -> anyhow::Result<Vec<OutMsg>> {
    let status = match db.claim_email(chat_id, raw, cfg.email_trial_days).await {
        Ok(status) => status,
        Err(error) => {
            tracing::error!(%error, "trial de e-mail");
            *session = Session::menu();
            return Ok(vec![
                text("Não consegui ativar o trial agora."),
                menu_message(),
            ]);
        }
    };
    let messages = match status {
        ClaimStatus::InvalidEmail => {
            return Ok(vec![text(
                "E-mail inválido. Envie de novo, ou *menu* para voltar.",
            )]);
        }
        ClaimStatus::EmailTaken => {
            *session = Session::menu();
            vec![
                text("Esse e-mail já foi usado em outra conta."),
                menu_message(),
            ]
        }
        ClaimStatus::AlreadyClaimed => {
            *session = Session::menu();
            vec![
                text("Você já usou o trial de e-mail nesta conta."),
                menu_message(),
            ]
        }
        ClaimStatus::AlreadyPro => {
            *session = Session::menu();
            vec![text("✅ Você já tem o *Radar Pro* ativo."), menu_message()]
        }
        ClaimStatus::Activated { pro_until } => {
            *session = Session::menu();
            vec![text(pro_activated(pro_until, cfg)), menu_message()]
        }
    };
    Ok(messages)
}

enum Nav {
    Next,
    Prev,
    Third,
    Menu,
    Unknown,
}

fn nav_action(raw: &str) -> Nav {
    match raw.trim() {
        "1" => Nav::Next,
        "2" => Nav::Prev,
        "3" => Nav::Third,
        "4" => Nav::Menu,
        other => {
            let norm = normalize_text(other);
            if norm == "proximo" || norm == "proxima" {
                Nav::Next
            } else if norm == "anterior" {
                Nav::Prev
            } else {
                Nav::Unknown
            }
        }
    }
}

pub fn should_show_typing(text: &str) -> bool {
    let norm = normalize_text(text);
    norm.split_whitespace().count() >= 3 && global_command(text).is_none()
}

#[allow(dead_code)]
pub fn baseline_price(listing: &Listing) -> Option<i64> {
    effective_listing_price(
        listing.price_value.map(i64::from),
        &listing.listing_kind,
        json_fee(&listing.properties, "condominio"),
        json_fee(&listing.properties, "iptu"),
    )
}

#[cfg(test)]
mod card_botoes {
    use super::{card_buttons, interactive};

    #[test]
    fn nunca_passa_do_limite_da_whatsapp() {
        for (index, total) in [(0usize, 5usize), (2, 5), (4, 5), (0, 1)] {
            let itens = card_buttons(index, total);
            assert!(
                itens.len() <= interactive::MAX_BUTTONS,
                "{index}/{total} pediu {} botões",
                itens.len()
            );
            // O que não vira botão continua alcançável pelo número digitado.
            assert!(itens.iter().any(|item| item.label == "Menu"));
            assert!(itens.iter().any(|item| item.label == "Acompanhar"));
        }
    }

    #[test]
    fn primeiro_card_oferece_proximo_e_ultimo_oferece_anterior() {
        assert_eq!(card_buttons(0, 5)[0].id, "1");
        assert_eq!(card_buttons(4, 5)[0].id, "2");
        // Card único: navegar não faz sentido, sobram acompanhar e menu.
        assert_eq!(card_buttons(0, 1).len(), 2);
    }
}
