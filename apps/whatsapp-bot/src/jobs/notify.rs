use std::collections::HashMap;
use std::time::Duration;

use async_trait::async_trait;
use chrono::{DateTime, NaiveDate, NaiveTime, TimeZone, Utc};
use crate::config::Config;
use crate::db::Db;
use crate::handlers::OutMsg;
use crate::intelligence::prepare_match_carousel;
use crate::models::Listing;
use crate::money::{effective_listing_price, json_fee};
use crate::session::Step;
use crate::ui::{card_caption, plain, watch_back, watch_price_change, watch_removed};

#[async_trait]
pub trait Sender: Send + Sync {
    async fn send_to(&self, jid: &str, messages: &[OutMsg]) -> anyhow::Result<()>;
}

pub fn due<Tz: TimeZone>(now: DateTime<Tz>, last: Option<NaiveDate>) -> bool {
    let gate = NaiveTime::from_hms_opt(10, 0, 0).unwrap();
    last != Some(now.date_naive()) && now.time() >= gate
}

pub fn read_stamp(path: &str) -> Option<NaiveDate> {
    let raw = std::fs::read_to_string(path).ok()?;
    NaiveDate::parse_from_str(raw.trim(), "%Y-%m-%d").ok()
}

pub fn write_stamp(path: &str, day: NaiveDate) -> anyhow::Result<()> {
    if let Some(parent) = std::path::Path::new(path).parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }
    std::fs::write(path, day.format("%Y-%m-%d").to_string())?;
    Ok(())
}

pub async fn run_daily(db: &Db, sender: &dyn Sender, cfg: &Config) -> anyhow::Result<()> {
    let users = db.whatsapp_users().await?;
    let jids: HashMap<i64, String> = users
        .iter()
        .filter_map(|user| {
            user.whatsapp_jid
                .clone()
                .map(|jid| (user.chat_id, jid))
        })
        .collect();
    let ttl = Duration::from_secs((cfg.session_ttl_hours.max(1) as u64) * 3600);
    for user in &users {
        let Some(jid) = jids.get(&user.chat_id) else {
            continue;
        };
        if let Err(error) = notify_user(db, sender, cfg, user.chat_id, jid, ttl).await {
            tracing::error!(%error, chat_id = user.chat_id, "notificação de matches");
        }
        tokio::time::sleep(Duration::from_secs(2)).await;
    }
    if let Err(error) = notify_watches(db, sender, &jids).await {
        tracing::error!(%error, "notificação de watchlist");
    }
    Ok(())
}

async fn notify_user(
    db: &Db,
    sender: &dyn Sender,
    _cfg: &Config,
    chat_id: i64,
    jid: &str,
    ttl: Duration,
) -> anyhow::Result<()> {
    let rows = db.unnotified(chat_id).await?;
    if rows.is_empty() {
        return Ok(());
    }
    let alerts = db.active_alerts(chat_id).await?;
    let snapshot = db.snapshot().await.ok().flatten();
    let ranked = prepare_match_carousel(&rows, &alerts, snapshot.as_ref(), Utc::now());
    let pairs: Vec<(i32, i32)> = rows
        .iter()
        .map(|row| (row.alert_id, row.listing.listing_id))
        .collect();
    let session = db.load_session(chat_id, ttl).await.unwrap_or(None);
    let busy = session.as_ref().is_some_and(|current| {
        !matches!(
            current.step,
            Step::Menu | Step::MatchCarousel { .. }
        )
    });
    if busy {
        let mut lines = vec!["🔔 *Imóveis novos*".to_string(), String::new()];
        for item in ranked.iter().take(8) {
            lines.push(format!(
                "• {} — {}",
                plain(&item.listing.title),
                item.listing.url
            ));
        }
        if ranked.len() > 8 {
            lines.push(format!("e mais {}.", ranked.len() - 8));
        }
        sender.send_to(jid, &[OutMsg::Text(lines.join("\n"))]).await?;
    } else {
        let ids: Vec<i32> = ranked.iter().map(|item| item.listing.listing_id).collect();
        let mut session = session.unwrap_or_else(crate::session::Session::menu);
        session.step = Step::MatchCarousel {
            index: 0,
            listing_ids: ids,
        };
        db.save_session(chat_id, &session).await?;
        let mut messages = vec![OutMsg::Text(
            "🔔 *Imóveis novos para os seus alertas*".to_string(),
        )];
        if let Some(first) = ranked.first() {
            messages.push(card_message(&first.listing, 0, ranked.len(), Some(&first.headline)));
        }
        sender.send_to(jid, &messages).await?;
    }
    db.mark_notified(&pairs).await?;
    Ok(())
}

fn card_message(listing: &Listing, index: usize, total: usize, headline: Option<&str>) -> OutMsg {
    let caption = card_caption(listing, index, total, headline);
    if let Some(url) = listing.images.iter().find(|url| url.starts_with("http")) {
        OutMsg::Image {
            url: url.clone(),
            caption,
        }
    } else {
        OutMsg::Text(caption)
    }
}

async fn notify_watches(
    db: &Db,
    sender: &dyn Sender,
    jids: &HashMap<i64, String>,
) -> anyhow::Result<()> {
    let rows = db.changed_watches_whatsapp().await?;
    let mut baselines = Vec::new();
    let mut last_chat = None;
    for watch in rows {
        let Some(jid) = jids.get(&watch.chat_id) else {
            continue;
        };
        if last_chat != Some(watch.chat_id) {
            if last_chat.is_some() {
                tokio::time::sleep(Duration::from_secs(2)).await;
            }
            last_chat = Some(watch.chat_id);
        }
        let listing = &watch.listing;
        let current = effective_listing_price(
            listing.price_value.map(i64::from),
            &listing.listing_kind,
            json_fee(&listing.properties, "condominio"),
            json_fee(&listing.properties, "iptu"),
        );
        let title = plain(&listing.title);
        let mut messages = Vec::new();
        if current != watch.last_known_price.map(i64::from) {
            messages.push(OutMsg::Text(watch_price_change(
                &title,
                watch.last_known_price.map(i64::from),
                current,
                &listing.url,
            )));
        }
        if listing.active != watch.last_known_active {
            if listing.active {
                messages.push(OutMsg::Text(watch_back(&title, &listing.url)));
            } else {
                messages.push(OutMsg::Text(watch_removed(&title, &listing.url)));
            }
        }
        if !messages.is_empty() {
            sender.send_to(jid, &messages).await?;
            tokio::time::sleep(Duration::from_millis(500)).await;
        }
        baselines.push((watch.id, current.map(|value| value as i32), listing.active));
    }
    db.update_watch_baselines(&baselines).await?;
    Ok(())
}

pub fn now_maceio() -> DateTime<chrono_tz::Tz> {
    Utc::now().with_timezone(&chrono_tz::Tz::America__Maceio)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;
    use chrono_tz::America::Maceio;

    #[test]
    fn runs_once_after_ten() {
        let morning = Maceio.with_ymd_and_hms(2026, 9, 23, 9, 30, 0).unwrap();
        let ten = Maceio.with_ymd_and_hms(2026, 9, 23, 10, 5, 0).unwrap();
        assert!(!due(morning, None));
        assert!(due(ten, None));
        assert!(!due(ten, Some(ten.date_naive())));
    }
}
