use std::time::Duration;

use anyhow::{anyhow, Context};

#[derive(Debug, Clone)]
pub struct Config {
    pub database_url: String,
    pub session_path: String,
    pub pair_secret: String,
    pub port: u16,
    pub llm_provider: String,
    pub llm_model: String,
    pub openai_api_key: String,
    pub llm_timeout: Duration,
    pub assistant_memory_turns: usize,
    pub assistant_memory_ttl_seconds: i64,
    pub assistant_max_message_chars: usize,
    pub assistant_free_messages_per_day: i32,
    pub assistant_pro_messages_per_day: i32,
    pub assistant_free_audio_per_day: i32,
    pub assistant_pro_audio_per_day: i32,
    pub assistant_max_audio_seconds: u32,
    pub assistant_max_audio_bytes: usize,
    pub assistant_daily_token_alert: i64,
    pub public_site_url: String,
    pub support_url: String,
    pub render_external_url: String,
    pub alert_nl_enabled: bool,
    pub watch_free_cap: i64,
    pub watch_pro_cap: i64,
    pub alert_free_cap: i64,
    pub alert_pro_cap: i64,
    pub email_trial_days: i64,
    pub session_ttl_hours: i64,
    pub notify_stamp_path: String,
    pub log_level: String,
}

impl Config {
    pub fn from_env() -> anyhow::Result<Self> {
        let _ = dotenvy::dotenv();
        let database_url =
            normalize_database_url(&std::env::var("DATABASE_URL").unwrap_or_else(|_| {
                "postgresql://postgres:teste123@localhost:5432/imovel_radar".to_string()
            }));
        if database_url.is_empty() {
            return Err(anyhow!("DATABASE_URL vazio"));
        }
        let session_path = std::env::var("WHATSAPP_SESSION_PATH")
            .unwrap_or_else(|_| "/data/whatsapp.db".to_string());
        let notify_stamp_path = std::env::var("NOTIFY_STAMP_PATH").unwrap_or_else(|_| {
            let parent = std::path::Path::new(&session_path)
                .parent()
                .unwrap_or_else(|| std::path::Path::new("/data"));
            parent.join("last_notify.txt").display().to_string()
        });
        let port = std::env::var("PORT")
            .ok()
            .and_then(|raw| raw.parse().ok())
            .unwrap_or(10000);
        let timeout_secs = std::env::var("LLM_TIMEOUT_SECONDS")
            .ok()
            .and_then(|raw| raw.parse::<f64>().ok())
            .unwrap_or(8.0);
        Ok(Self {
            database_url,
            session_path,
            pair_secret: std::env::var("PAIR_SECRET").unwrap_or_default(),
            port,
            llm_provider: std::env::var("LLM_PROVIDER")
                .unwrap_or_else(|_| "mock".to_string())
                .trim()
                .to_lowercase(),
            llm_model: std::env::var("LLM_MODEL").unwrap_or_else(|_| "gpt-4o-mini".to_string()),
            openai_api_key: std::env::var("OPENAI_API_KEY").unwrap_or_default(),
            llm_timeout: Duration::from_secs_f64(timeout_secs.max(1.0)),
            assistant_memory_turns: env_i64("ASSISTANT_MEMORY_TURNS", 6).clamp(1, 20) as usize,
            assistant_memory_ttl_seconds: env_i64("ASSISTANT_MEMORY_TTL_SECONDS", 14_400).max(60),
            assistant_max_message_chars: env_i64("ASSISTANT_MAX_MESSAGE_CHARS", 4_000)
                .clamp(100, 10_000) as usize,
            assistant_free_messages_per_day: env_i64("ASSISTANT_FREE_MESSAGES_PER_DAY", 50)
                .clamp(1, 10_000) as i32,
            assistant_pro_messages_per_day: env_i64("ASSISTANT_PRO_MESSAGES_PER_DAY", 300)
                .clamp(1, 50_000) as i32,
            assistant_free_audio_per_day: env_i64("ASSISTANT_FREE_AUDIO_PER_DAY", 5).clamp(0, 1_000)
                as i32,
            assistant_pro_audio_per_day: env_i64("ASSISTANT_PRO_AUDIO_PER_DAY", 30).clamp(0, 5_000)
                as i32,
            assistant_max_audio_seconds: env_i64("ASSISTANT_MAX_AUDIO_SECONDS", 120).clamp(1, 600)
                as u32,
            assistant_max_audio_bytes: env_i64("ASSISTANT_MAX_AUDIO_BYTES", 20 * 1024 * 1024)
                .clamp(1_024, 100 * 1024 * 1024) as usize,
            assistant_daily_token_alert: env_i64("ASSISTANT_DAILY_TOKEN_ALERT", 100_000).max(1),
            public_site_url: std::env::var("PUBLIC_SITE_URL")
                .unwrap_or_else(|_| "https://imovel-radar.vercel.app".to_string())
                .trim_end_matches('/')
                .to_string(),
            support_url: std::env::var("SUPPORT_URL")
                .unwrap_or_default()
                .trim()
                .to_string(),
            render_external_url: std::env::var("RENDER_EXTERNAL_URL")
                .unwrap_or_default()
                .trim()
                .to_string(),
            alert_nl_enabled: env_bool("ALERT_NL_ENABLED", true),
            watch_free_cap: env_i64("WATCHLIST_FREE_CAP", 2),
            watch_pro_cap: env_i64("WATCHLIST_PRO_CAP", 10),
            alert_free_cap: env_i64("ALERT_FREE_CAP", 1),
            alert_pro_cap: env_i64("ALERT_PRO_CAP", 5),
            email_trial_days: env_i64("EMAIL_PRO_TRIAL_DAYS", 30),
            session_ttl_hours: env_i64("SESSION_TTL_HOURS", 4),
            notify_stamp_path,
            log_level: std::env::var("LOG_LEVEL")
                .unwrap_or_else(|_| "INFO".to_string())
                .to_lowercase(),
        })
    }

    pub fn log_filter(&self) -> String {
        format!("whatsapp_bot={},whatsapp_rust=info", self.log_level)
    }
}

pub fn normalize_database_url(url: &str) -> String {
    let url = url.trim();
    for prefix in [
        "postgresql+psycopg2://",
        "postgresql+psycopg://",
        "postgres://",
    ] {
        if let Some(rest) = url.strip_prefix(prefix) {
            return format!("postgresql://{rest}");
        }
    }
    url.to_string()
}

fn env_bool(name: &str, default: bool) -> bool {
    match std::env::var(name) {
        Ok(raw) => matches!(
            raw.trim().to_lowercase().as_str(),
            "1" | "true" | "yes" | "on"
        ),
        Err(_) => default,
    }
}

fn env_i64(name: &str, default: i64) -> i64 {
    std::env::var(name)
        .ok()
        .and_then(|raw| raw.trim().parse().ok())
        .unwrap_or(default)
}

pub fn tokens_match(provided: &str, expected: &str) -> bool {
    let provided = provided.as_bytes();
    let expected = expected.as_bytes();
    if provided.len() != expected.len() || expected.is_empty() {
        return false;
    }
    let mut diff = 0u8;
    for (left, right) in provided.iter().zip(expected) {
        diff |= left ^ right;
    }
    diff == 0
}

pub fn ensure_parent_dir(path: &str) -> anyhow::Result<()> {
    if let Some(parent) = std::path::Path::new(path).parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)
                .with_context(|| format!("criar diretório {}", parent.display()))?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalizes_sqlalchemy_urls() {
        assert_eq!(
            normalize_database_url("postgresql+psycopg://u:p@localhost/db"),
            "postgresql://u:p@localhost/db"
        );
        assert_eq!(
            normalize_database_url("postgres://u:p@localhost/db"),
            "postgresql://u:p@localhost/db"
        );
    }

    #[test]
    fn token_compare_rejects_different_lengths() {
        assert!(!tokens_match("abc", "abcd"));
        assert!(tokens_match("segredo", "segredo"));
        assert!(!tokens_match("segredo", ""));
    }
}
