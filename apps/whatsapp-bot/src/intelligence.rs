use chrono::{DateTime, Duration, Utc};
use serde_json::Value;

use crate::models::{Alert, Listing, ListingMatch};
use crate::money::{format_brl, json_fee, json_int, effective_listing_price};

const FRESH_HOURS: i64 = 36;
const HIGH_MATCH_MIN: i32 = 90;
const BELOW_AVG_RATIO: f64 = 0.95;
const RENT_MIN_DROP: i64 = 50;
const SALE_MIN_DROP: i64 = 1_000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) enum EventPriority {
    PriceDrop = 0,
    BackOnMarket = 1,
    BelowAverage = 2,
    HighMatch = 3,
    Fresh = 4,
    New = 5,
}

#[derive(Debug, Clone)]
pub struct RankedListing {
    pub listing: Listing,
    pub headline: String,
}

fn aware(value: DateTime<Utc>) -> DateTime<Utc> {
    value
}

fn total_price(listing: &Listing) -> Option<i64> {
    effective_listing_price(
        listing.price_value.map(i64::from),
        &listing.listing_kind,
        json_fee(&listing.properties, "condominio"),
        json_fee(&listing.properties, "iptu"),
    )
}

pub fn format_drop_amount(amount: i64) -> String {
    if amount >= 1000 && amount % 1000 == 0 {
        return format!("R$ {} mil", amount / 1000);
    }
    let formatted = format_brl(Some(amount));
    if let Some(stripped) = formatted.strip_suffix(",00") {
        stripped.to_string()
    } else {
        formatted
    }
}

pub fn format_published_ago(first_seen_at: DateTime<Utc>, now: DateTime<Utc>) -> String {
    let seconds = (now - first_seen_at).num_seconds().max(0);
    let minutes = seconds / 60;
    let hours = minutes / 60;
    let days = hours / 24;
    if minutes < 1 {
        "há instantes".to_string()
    } else if minutes == 1 {
        "há 1 minuto".to_string()
    } else if minutes < 60 {
        format!("há {minutes} minutos")
    } else if hours == 1 {
        "há 1 hora".to_string()
    } else if hours < 24 {
        format!("há {hours} horas")
    } else if days == 1 {
        "ontem".to_string()
    } else {
        format!("há {days} dias")
    }
}

pub fn match_score(listing: &Listing, alert: &Alert) -> i32 {
    let price = total_price(listing);
    let min_price = alert.min_price.map(i64::from);
    let max_price = alert.max_price.map(i64::from);
    let price_pts = match (price, min_price, max_price) {
        (None, _, _) => 20.0,
        (Some(price), Some(min_price), Some(max_price)) => {
            let span = (max_price - min_price).max(1) as f64;
            let t = ((price - min_price) as f64 / span).clamp(0.0, 1.0);
            45.0 - 30.0 * t
        }
        (Some(price), None, Some(max_price)) => {
            let floor = 0.7 * max_price as f64;
            let span = ((max_price as f64) - floor).max(1.0);
            let t = ((price as f64 - floor) / span).clamp(0.0, 1.0);
            45.0 - 30.0 * t
        }
        (Some(_), _, None) => 30.0,
    };
    let nbhd_pts = if alert.neighbourhoods.is_empty() {
        12.0
    } else {
        25.0
    };
    let rooms = json_int(&listing.properties, "rooms");
    let rooms_pts = match (alert.min_rooms, rooms) {
        (None, Some(_)) => 12.0,
        (None, None) => 8.0,
        (Some(_), None) => 8.0,
        (Some(min_rooms), Some(rooms)) if rooms > i64::from(min_rooms) => 18.0,
        (Some(_), Some(_)) => 14.0,
    };
    let cat_pts = if alert.categories.is_empty() { 6.0 } else { 12.0 };
    (price_pts + nbhd_pts + rooms_pts + cat_pts).round() as i32
}

pub fn neighbourhood_median_price(
    snapshot: Option<&Value>,
    municipality: &str,
    listing_kind: &str,
    neighbourhood: &str,
) -> Option<i64> {
    let snapshot = snapshot?;
    if neighbourhood.is_empty() {
        return None;
    }
    let cities = snapshot.get("cities")?.as_array()?;
    for city in cities {
        if city.get("municipality").and_then(|v| v.as_str()) != Some(municipality) {
            continue;
        }
        let kind_stats = city.get("kinds")?.get(listing_kind)?;
        let rows = kind_stats.get("neighbourhoods")?.as_array()?;
        for row in rows {
            if row.get("name").and_then(|v| v.as_str()) != Some(neighbourhood) {
                continue;
            }
            if row.get("ranked").and_then(|v| v.as_bool()) != Some(true) {
                return None;
            }
            return row.get("median_price").and_then(|v| v.as_i64());
        }
        return None;
    }
    None
}

fn price_drop_amount(listing: &Listing) -> Option<i64> {
    let old_price = listing.old_price.map(i64::from)?;
    let new_price = listing.price_value.map(i64::from)?;
    if old_price <= new_price {
        return None;
    }
    let drop = old_price - new_price;
    let minimum = if listing.listing_kind == "venda" {
        SALE_MIN_DROP
    } else {
        RENT_MIN_DROP
    };
    (drop >= minimum).then_some(drop)
}

fn is_fresh(listing: &Listing, now: DateTime<Utc>) -> bool {
    listing
        .first_seen_at
        .map(|seen| now - aware(seen) <= Duration::hours(FRESH_HOURS))
        .unwrap_or(false)
}

fn is_back_on_market(listing: &Listing, alert: &Alert, now: DateTime<Utc>) -> bool {
    let (Some(created), Some(first_seen)) = (alert.created_at, listing.first_seen_at) else {
        return false;
    };
    if now - created < Duration::hours(FRESH_HOURS) {
        return false;
    }
    if now - first_seen < Duration::hours(FRESH_HOURS) {
        return false;
    }
    true
}

pub(crate) fn classify_headline(
    listing: &Listing,
    alert: &Alert,
    snapshot: Option<&Value>,
    now: DateTime<Utc>,
) -> (EventPriority, String, i32) {
    let score = match_score(listing, alert);
    if let Some(drop) = price_drop_amount(listing) {
        return (
            EventPriority::PriceDrop,
            format!("📉 Preço caiu {}", format_drop_amount(drop)),
            score,
        );
    }
    if is_back_on_market(listing, alert, now) {
        return (
            EventPriority::BackOnMarket,
            "👀 Esse imóvel voltou a ficar disponível".to_string(),
            score,
        );
    }
    let asked = listing.price_value.map(i64::from);
    let median = neighbourhood_median_price(
        snapshot,
        &listing.municipality,
        &listing.listing_kind,
        &listing.neighbourhood,
    );
    if let (Some(asked), Some(median)) = (asked, median) {
        if (asked as f64) <= median as f64 * BELOW_AVG_RATIO {
            return (
                EventPriority::BelowAverage,
                "🏷️ Preço abaixo da média da região".to_string(),
                score,
            );
        }
    }
    if score >= HIGH_MATCH_MIN {
        return (
            EventPriority::HighMatch,
            format!("🔥 Novo imóvel com {score}% de match"),
            score,
        );
    }
    if is_fresh(listing, now) {
        let ago = listing
            .first_seen_at
            .map(|seen| format_published_ago(seen, now))
            .unwrap_or_else(|| "há pouco".to_string());
        return (
            EventPriority::Fresh,
            format!("⚡ Anúncio publicado {ago}"),
            score,
        );
    }
    (
        EventPriority::New,
        "🚨 Novo imóvel encontrado".to_string(),
        score,
    )
}

pub fn prepare_match_carousel(
    rows: &[ListingMatch],
    alerts: &[Alert],
    snapshot: Option<&Value>,
    now: DateTime<Utc>,
) -> Vec<RankedListing> {
    let mut scored = Vec::new();
    for (index, row) in rows.iter().enumerate() {
        let (priority, headline, score) = if let Some(alert) =
            alerts.iter().find(|alert| alert.id == row.alert_id)
        {
            classify_headline(&row.listing, alert, snapshot, now)
        } else {
            (
                EventPriority::New,
                "🚨 Novo imóvel encontrado".to_string(),
                0,
            )
        };
        scored.push((
            priority,
            -score,
            row.listing.listing_id,
            index,
            row.listing.clone(),
            headline,
        ));
    }
    scored.sort_by_key(|item| (item.0, item.1, item.2, item.3));
    scored
        .into_iter()
        .map(|(_, _, _, _, listing, headline)| RankedListing { listing, headline })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn listing() -> Listing {
        Listing {
            listing_id: 1,
            active: true,
            listing_kind: "aluguel".into(),
            url: "https://ex".into(),
            title: "Apto".into(),
            price_value: Some(900),
            old_price: Some(1200),
            municipality: "Maceió".into(),
            neighbourhood: "Ponta Verde".into(),
            category: "Apartamentos".into(),
            images: vec!["https://img".into()],
            properties: serde_json::json!({}),
            first_seen_at: Some(Utc.with_ymd_and_hms(2026, 9, 1, 0, 0, 0).unwrap()),
        }
    }

    fn alert() -> Alert {
        Alert {
            id: 1,
            chat_id: 1,
            alert_name: Some("Apto".into()),
            listing_kind: "aluguel".into(),
            municipality: "Maceió".into(),
            min_price: Some(0),
            max_price: Some(2000),
            min_rooms: None,
            neighbourhoods: vec!["Ponta Verde".into()],
            categories: vec!["Apartamentos".into()],
            active: true,
            created_at: Some(Utc.with_ymd_and_hms(2026, 8, 1, 0, 0, 0).unwrap()),
        }
    }

    #[test]
    fn price_drop_wins() {
        let now = Utc.with_ymd_and_hms(2026, 9, 23, 12, 0, 0).unwrap();
        let (_, headline, _) = classify_headline(&listing(), &alert(), None, now);
        assert!(headline.contains("Preço caiu"));
    }
}
