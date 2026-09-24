use chrono::{DateTime, Utc};
use serde_json::Value;

#[derive(Debug, Clone)]
pub struct User {
    pub chat_id: i64,
    pub plan: String,
    pub pro_until: Option<DateTime<Utc>>,
    pub email: Option<String>,
    pub email_pro_trial_claimed_at: Option<DateTime<Utc>>,
    pub channel: String,
    pub whatsapp_jid: Option<String>,
}

#[derive(Debug, Clone)]
pub struct Listing {
    pub listing_id: i32,
    pub active: bool,
    pub listing_kind: String,
    pub url: String,
    pub title: String,
    pub price_value: Option<i32>,
    pub old_price: Option<i32>,
    pub municipality: String,
    pub neighbourhood: String,
    pub category: String,
    pub images: Vec<String>,
    pub properties: Value,
    pub first_seen_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone)]
pub struct Alert {
    pub id: i32,
    pub chat_id: i64,
    pub alert_name: Option<String>,
    pub listing_kind: String,
    pub municipality: String,
    pub min_price: Option<i32>,
    pub max_price: Option<i32>,
    pub min_rooms: Option<i32>,
    pub neighbourhoods: Vec<String>,
    pub categories: Vec<String>,
    pub active: bool,
    pub created_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone)]
pub struct ListingMatch {
    pub listing: Listing,
    pub alert_id: i32,
}

#[derive(Debug, Clone)]
pub struct Watch {
    pub id: i32,
    pub chat_id: i64,
    pub listing_id: i32,
    pub last_known_price: Option<i32>,
    pub last_known_active: bool,
    pub listing: Listing,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CreateAlertStatus {
    Created(i32),
    Reused(i32),
    CapReached,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WatchStatus {
    Created(i32),
    Duplicate(i32),
    CapReached,
    ListingMissing,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ClaimStatus {
    Activated { pro_until: DateTime<Utc> },
    AlreadyPro,
    AlreadyClaimed,
    EmailTaken,
    InvalidEmail,
}

pub fn json_strings(value: Option<&Value>) -> Vec<String> {
    let Some(value) = value else {
        return Vec::new();
    };
    match value {
        Value::Array(items) => items
            .iter()
            .filter_map(|item| item.as_str().map(|text| text.to_string()))
            .collect(),
        Value::String(raw) => serde_json::from_str(raw).unwrap_or_default(),
        _ => Vec::new(),
    }
}

pub fn image_urls(images: &[String]) -> Vec<String> {
    images
        .iter()
        .filter(|url| url.starts_with("http"))
        .cloned()
        .collect()
}
