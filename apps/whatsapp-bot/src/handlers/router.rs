use std::time::Duration;

use chrono::Utc;

use crate::ai::{extract_alert_intent, match_neighbourhoods};
use crate::config::Config;
use crate::db::Db;
use crate::intelligence::prepare_match_carousel;
use crate::models::{ClaimStatus, CreateAlertStatus, Listing, WatchStatus};
use crate::money::{effective_listing_price, json_fee};
use crate::session::{
    global_command, normalize_text, parse_index_list, parse_money, Draft, GlobalCommand, Session,
    Step,
};
use crate::ui::{
    alert_detail, alerts_list, auto_alert_name, cap_alerts, cap_watches, card_caption,
    categories_prompt, category_options, city_prompt, confirm_prompt, edit_stub, help_text,
    intent_prompt, kind_prompt, main_menu, name_prompt, neighbourhoods_prompt, price_max_prompt,
    price_min_prompt, price_presets, price_prompt, pro_activated, pro_pitch, rooms_prompt,
    watch_card_caption,
};

#[derive(Debug, Clone)]
pub enum OutMsg {
    Text(String),
    Image { url: String, caption: String },
}

fn text(body: impl Into<String>) -> OutMsg {
    OutMsg::Text(body.into())
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
        return store(db, chat_id, &session, vec![text(main_menu())]).await;
    }

    if let Some(command) = global_command(raw) {
        return on_global(db, cfg, chat_id, &mut session, command).await;
    }

    let step = session.step.clone();
    let messages = match step {
        Step::Menu => on_menu(db, cfg, chat_id, &mut session, raw).await?,
        Step::Intent => on_intent(db, cfg, http, chat_id, &mut session, raw).await?,
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
        Step::Alerts { ids } => on_alerts(db, chat_id, &mut session, raw, &ids).await?,
        Step::AlertDetail { id } => on_alert_detail(db, chat_id, &mut session, raw, id).await?,
        Step::Email => on_email(db, cfg, chat_id, &mut session, raw).await?,
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
    if let Err(error) = db.save_session(chat_id, session).await {
        tracing::error!(%error, "falha ao gravar sessão");
    }
    Ok(messages)
}

async fn on_global(
    db: &Db,
    cfg: &Config,
    chat_id: i64,
    session: &mut Session,
    command: GlobalCommand,
) -> anyhow::Result<Vec<OutMsg>> {
    let messages = match command {
        GlobalCommand::Menu => {
            *session = Session::menu();
            vec![text(main_menu())]
        }
        GlobalCommand::Cancel => {
            let in_flow = !matches!(session.step, Step::Menu);
            *session = Session::menu();
            if in_flow {
                vec![text("Criação cancelada."), text(main_menu())]
            } else {
                vec![text(main_menu())]
            }
        }
        GlobalCommand::Help => {
            session.step = Step::Menu;
            vec![text(help_text()), text(main_menu())]
        }
        GlobalCommand::NewAlert => start_alert(cfg, session),
        GlobalCommand::MyAlerts => list_alerts(db, chat_id, session).await?,
        GlobalCommand::Watching => list_watches(db, chat_id, session).await?,
        GlobalCommand::Pro => start_email(db, cfg, chat_id, session).await?,
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
    chat_id: i64,
    session: &mut Session,
    raw: &str,
) -> anyhow::Result<Vec<OutMsg>> {
    match raw.trim() {
        "1" => Ok(start_alert(cfg, session)),
        "2" => list_alerts(db, chat_id, session).await,
        "3" => list_watches(db, chat_id, session).await,
        "4" => {
            session.step = Step::Menu;
            Ok(vec![text(help_text()), text(main_menu())])
        }
        "5" => start_email(db, cfg, chat_id, session).await,
        _ => Ok(vec![text("Não entendi. Responda com um número de 1 a 5."), text(main_menu())]),
    }
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
        return Ok(vec![text("Manda uma frase sobre o imóvel, ou *1* para o passo a passo.")]);
    };
    session.draft.nl_mode = true;
    if matches!(extracted.municipality.as_deref(), Some("Maceió" | "Recife" | "Natal")) {
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
        return vec![text("📍 *Em qual cidade você procura?*\n1. Maceió\n2. Recife\n3. Natal")];
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
    vec![text(confirm_prompt(&session.draft))]
}

async fn apply_neighbourhoods(
    db: &Db,
    session: &mut Session,
    raw: &[String],
) -> anyhow::Result<()> {
    let city = session.draft.municipality.clone().unwrap_or_else(|| "Maceió".into());
    let available = db
        .neighbourhoods(&city, session.draft.listing_kind.as_deref())
        .await
        .unwrap_or_default();
    session.draft.neighbourhoods = match_neighbourhoods(Some(raw), &available);
    session.draft.pending_raw_neighbourhoods.clear();
    Ok(())
}

async fn on_city(db: &Db, session: &mut Session, raw: &str) -> anyhow::Result<Vec<OutMsg>> {
    let city = match raw.trim() {
        "1" => "Maceió",
        "2" => "Recife",
        "3" => "Natal",
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
    Ok(vec![text(format!("📍 *Cidade:* {city}")), text(kind_prompt())])
}

fn on_kind(session: &mut Session, raw: &str) -> Vec<OutMsg> {
    let kind = match raw.trim() {
        "1" => "aluguel",
        "2" => "venda",
        _ => return vec![text("Responda 1 para alugar ou 2 para comprar."), text(kind_prompt())],
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
            return vec![text("Número fora da lista."), text(categories_prompt(kind, &session.draft.categories))];
        };
        if let Some(pos) = session.draft.categories.iter().position(|item| item == value) {
            session.draft.categories.remove(pos);
        } else {
            session.draft.categories.push((*value).to_string());
        }
    }
    vec![text(categories_prompt(kind, &session.draft.categories))]
}

fn on_price(session: &mut Session, raw: &str) -> Vec<OutMsg> {
    let kind = session.draft.listing_kind.clone().unwrap_or_else(|| "aluguel".into());
    let city = session.draft.municipality.clone().unwrap_or_else(|| "Maceió".into());
    if raw.trim() == "5" || normalize_text(raw) == "personalizado" {
        session.step = Step::PriceMin;
        return vec![text(price_min_prompt())];
    }
    let presets = price_presets(&kind, &city);
    let Ok(index) = raw.trim().parse::<usize>() else {
        return vec![text("Escolha um número da lista."), text(price_prompt(&kind, &city))];
    };
    let Some(preset) = presets.get(index - 1) else {
        return vec![text("Escolha um número da lista."), text(price_prompt(&kind, &city))];
    };
    session.draft.min_price = Some(preset.min);
    session.draft.max_price = Some(preset.max);
    after_price(session)
}

fn on_price_min(session: &mut Session, raw: &str) -> Vec<OutMsg> {
    let Some(min_price) = parse_money(raw) else {
        return vec![text("Número inválido. Ex.: 150000"), text(price_min_prompt())];
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
        return vec![text("O preço máximo deve ser maior ou igual ao mínimo."), text(price_max_prompt())];
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
    let rooms = match raw.trim() {
        "1" => None,
        "2" => Some(1),
        "3" => Some(2),
        "4" => Some(3),
        "5" => Some(4),
        _ => return Ok(vec![text("Responda de 1 a 5."), text(rooms_prompt())]),
    };
    session.draft.min_rooms = rooms;
    let city = session.draft.municipality.clone().unwrap_or_else(|| "Maceió".into());
    let all = db
        .neighbourhoods(&city, session.draft.listing_kind.as_deref())
        .await
        .unwrap_or_default();
    session.step = Step::Neighbourhoods { page: 0 };
    Ok(vec![text(neighbourhoods_prompt(&all, 0, &session.draft.neighbourhoods))])
}

async fn on_neighbourhoods(
    db: &Db,
    session: &mut Session,
    raw: &str,
    page: usize,
) -> anyhow::Result<Vec<OutMsg>> {
    let city = session.draft.municipality.clone().unwrap_or_else(|| "Maceió".into());
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
        return Ok(vec![text(neighbourhoods_prompt(&all, page, &session.draft.neighbourhoods))]);
    }
    if norm == "voltar" || norm == "anterior" {
        page = page.saturating_sub(1);
        session.step = Step::Neighbourhoods { page };
        return Ok(vec![text(neighbourhoods_prompt(&all, page, &session.draft.neighbourhoods))]);
    }
    if raw.trim() == "0" || norm == "ok" || norm == "concluir" || norm == "todos" {
        session.draft.alert_name = Some(auto_alert_name(&session.draft));
        session.step = Step::Name;
        return Ok(vec![text(name_prompt(session.draft.alert_name.as_deref().unwrap_or("Alerta")))]);
    }
    if all.is_empty() {
        return Ok(vec![text(neighbourhoods_prompt(&all, page, &session.draft.neighbourhoods))]);
    }
    let Some(indexes) = parse_index_list(raw) else {
        return Ok(vec![text(neighbourhoods_prompt(&all, page, &session.draft.neighbourhoods))]);
    };
    let start = page * PAGE;
    for index in indexes {
        let Some(name) = all.get(start + index - 1) else {
            return Ok(vec![
                text("Número fora desta página."),
                text(neighbourhoods_prompt(&all, page, &session.draft.neighbourhoods)),
            ]);
        };
        if let Some(pos) = session.draft.neighbourhoods.iter().position(|item| item == name) {
            session.draft.neighbourhoods.remove(pos);
        } else {
            session.draft.neighbourhoods.push(name.clone());
        }
    }
    session.step = Step::Neighbourhoods { page };
    Ok(vec![text(neighbourhoods_prompt(&all, page, &session.draft.neighbourhoods))])
}

fn on_name(session: &mut Session, raw: &str) -> Vec<OutMsg> {
    let name = if raw.trim() == "1" {
        session.draft.alert_name.clone().unwrap_or_else(|| auto_alert_name(&session.draft))
    } else {
        let cleaned = raw.trim();
        if cleaned.chars().count() < 2 {
            return vec![text("Nome inválido. Tente de novo."), text(name_prompt(&auto_alert_name(&session.draft)))];
        }
        cleaned.chars().take(120).collect()
    };
    session.draft.alert_name = Some(name);
    session.step = Step::Confirm;
    vec![text(confirm_prompt(&session.draft))]
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
            return Ok(vec![text("Ok! O alerta não foi salvo."), text(main_menu())]);
        }
        "1" => {}
        _ => return Ok(vec![text("Responda *1* para confirmar ou *2* para cancelar.")]),
    }
    if session.draft.min_price.is_none() && session.draft.max_price.is_none() {
        session.step = Step::Price;
        return Ok(vec![text("Falta a faixa de preço."), text(price_prompt(
            session.draft.listing_kind.as_deref().unwrap_or("aluguel"),
            session.draft.municipality.as_deref().unwrap_or("Maceió"),
        ))]);
    }
    let status = match db.create_alert(chat_id, &session.draft, cfg).await {
        Ok(status) => status,
        Err(error) => {
            tracing::error!(%error, "criar alerta");
            return Ok(vec![text("Não consegui salvar seu alerta agora. Tente novamente em instantes.")]);
        }
    };
    match status {
        CreateAlertStatus::CapReached => {
            let user = db.get_user(chat_id).await.ok().flatten();
            let pro = Db::is_pro(user.as_ref(), Utc::now());
            *session = Session::menu();
            Ok(vec![text(cap_alerts(cfg, pro)), text(main_menu())])
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
        return Ok(vec![text(body), text(main_menu())]);
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
        messages.push(listing_message(&first.listing, 0, ranked.len(), Some(&first.headline)));
    }
    Ok(messages)
}

fn listing_message(listing: &Listing, index: usize, total: usize, headline: Option<&str>) -> OutMsg {
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
        return Ok(vec![text(main_menu())]);
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
            return Ok(vec![text(main_menu())]);
        }
        Nav::Unknown => {
            return Ok(vec![text(
                "1 próximo · 2 anterior · 3 acompanhar · 4 menu",
            )])
        }
    }
    session.step = Step::MatchCarousel {
        index,
        listing_ids: listing_ids.to_vec(),
    };
    let Some(listing) = db.listing(listing_ids[index]).await? else {
        return Ok(vec![text("Não achei esse anúncio.")]);
    };
    Ok(vec![listing_message(&listing, index, listing_ids.len(), None)])
}

async fn watch_reply(db: &Db, cfg: &Config, chat_id: i64, listing_id: i32) -> Vec<OutMsg> {
    match db.create_watch(chat_id, listing_id, cfg).await {
        Ok(WatchStatus::Created(_)) => vec![text("Anúncio adicionado. Aviso se o preço mudar ou se sair do ar.")],
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
    Ok(vec![text(alerts_list(&alerts))])
}

async fn on_alerts(
    db: &Db,
    chat_id: i64,
    session: &mut Session,
    raw: &str,
    ids: &[i32],
) -> anyhow::Result<Vec<OutMsg>> {
    if ids.is_empty() && raw.trim() == "1" {
        return Ok(start_alert_from_empty(session));
    }
    if ids.is_empty() {
        *session = Session::menu();
        return Ok(vec![text(main_menu())]);
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
    Ok(vec![text(alert_detail(&alert))])
}

fn start_alert_from_empty(session: &mut Session) -> Vec<OutMsg> {
    session.step = Step::Menu;
    vec![text("Digite *novo alerta* para criar o primeiro.")]
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
            let deleted = db.delete_alert(chat_id, id).await.unwrap_or(false);
            let note = if deleted {
                "Alerta removido."
            } else {
                "Não achei esse alerta."
            };
            let mut messages = vec![text(note)];
            messages.extend(list_alerts(db, chat_id, session).await?);
            Ok(messages)
        }
        "2" => {
            let name = db
                .alert_for_user(chat_id, id)
                .await?
                .and_then(|alert| alert.alert_name)
                .unwrap_or_else(|| "Sem nome".into());
            Ok(vec![text(edit_stub(&name))])
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
            text(main_menu()),
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
        return Ok(vec![text(main_menu())]);
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
            let removed = db.delete_watch(chat_id, watch_ids[index]).await.unwrap_or(false);
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
            return Ok(vec![text(main_menu())]);
        }
        Nav::Unknown => return Ok(vec![text("1 próximo · 2 anterior · 3 parar · 4 menu")]),
    }
    session.step = Step::WatchCarousel {
        index,
        watch_ids: watch_ids.to_vec(),
    };
    let watches = db.watches(chat_id).await?;
    let Some(watch) = watches.into_iter().find(|watch| watch.id == watch_ids[index]) else {
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
            text(main_menu()),
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
            return Ok(vec![text("Não consegui ativar o trial agora."), text(main_menu())]);
        }
    };
    let messages = match status {
        ClaimStatus::InvalidEmail => {
            return Ok(vec![text("E-mail inválido. Envie de novo, ou *menu* para voltar.")]);
        }
        ClaimStatus::EmailTaken => {
            *session = Session::menu();
            vec![text("Esse e-mail já foi usado em outra conta."), text(main_menu())]
        }
        ClaimStatus::AlreadyClaimed => {
            *session = Session::menu();
            vec![text("Você já usou o trial de e-mail nesta conta."), text(main_menu())]
        }
        ClaimStatus::AlreadyPro => {
            *session = Session::menu();
            vec![text("✅ Você já tem o *Radar Pro* ativo."), text(main_menu())]
        }
        ClaimStatus::Activated { pro_until } => {
            *session = Session::menu();
            vec![text(pro_activated(pro_until, cfg)), text(main_menu())]
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
