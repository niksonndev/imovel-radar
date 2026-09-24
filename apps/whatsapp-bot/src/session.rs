use serde::{Deserialize, Serialize};
use unicode_normalization::UnicodeNormalization;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Draft {
    pub municipality: Option<String>,
    pub listing_kind: Option<String>,
    #[serde(default)]
    pub categories: Vec<String>,
    pub min_price: Option<i64>,
    pub max_price: Option<i64>,
    pub min_rooms: Option<i32>,
    #[serde(default)]
    pub neighbourhoods: Vec<String>,
    pub alert_name: Option<String>,
    #[serde(default)]
    pub pending_raw_neighbourhoods: Vec<String>,
    #[serde(default)]
    pub nl_mode: bool,
}

impl Default for Draft {
    fn default() -> Self {
        Self {
            municipality: None,
            listing_kind: None,
            categories: Vec::new(),
            min_price: None,
            max_price: None,
            min_rooms: None,
            neighbourhoods: Vec::new(),
            alert_name: None,
            pending_raw_neighbourhoods: Vec::new(),
            nl_mode: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Step {
    Menu,
    Intent,
    City,
    Kind,
    Categories,
    Price,
    PriceMin,
    PriceMax,
    Rooms,
    Neighbourhoods { page: usize },
    Name,
    Confirm,
    Alerts { ids: Vec<i32> },
    AlertDetail { id: i32 },
    Email,
    MatchCarousel { index: usize, listing_ids: Vec<i32> },
    WatchCarousel { index: usize, watch_ids: Vec<i32> },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Session {
    pub step: Step,
    #[serde(default)]
    pub draft: Draft,
}

impl Session {
    pub fn menu() -> Self {
        Self {
            step: Step::Menu,
            draft: Draft::default(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GlobalCommand {
    Menu,
    NewAlert,
    MyAlerts,
    Watching,
    Help,
    Cancel,
    Pro,
}

pub fn normalize_text(text: &str) -> String {
    let folded = text
        .nfkd()
        .filter(|ch| !unicode_normalization::char::is_combining_mark(*ch))
        .collect::<String>()
        .to_lowercase();
    folded.split_whitespace().collect::<Vec<_>>().join(" ")
}

pub fn global_command(text: &str) -> Option<GlobalCommand> {
    let norm = normalize_text(text.trim().trim_start_matches('/'));
    match norm.as_str() {
        "menu" | "oi" | "ola" | "oie" | "inicio" | "comecar" | "start" => {
            Some(GlobalCommand::Menu)
        }
        "novo alerta" | "novo_alerta" | "novo" => Some(GlobalCommand::NewAlert),
        "meus alertas" | "alertas" => Some(GlobalCommand::MyAlerts),
        "acompanhando" | "watchlist" => Some(GlobalCommand::Watching),
        "ajuda" | "help" => Some(GlobalCommand::Help),
        "cancelar" | "cancela" | "sair" => Some(GlobalCommand::Cancel),
        "pro" | "radar pro" => Some(GlobalCommand::Pro),
        _ => None,
    }
}

pub fn parse_index_list(text: &str) -> Option<Vec<usize>> {
    let mut out = Vec::new();
    for part in text.split(|ch: char| matches!(ch, ',' | ';' | ' ')) {
        let part = part.trim();
        if part.is_empty() {
            continue;
        }
        let number: usize = part.parse().ok()?;
        if number == 0 {
            return None;
        }
        out.push(number);
    }
    if out.is_empty() {
        None
    } else {
        Some(out)
    }
}

pub fn parse_money(text: &str) -> Option<i64> {
    let norm = normalize_text(text);
    let digits: String = norm.chars().filter(|ch| ch.is_ascii_digit()).collect();
    if digits.is_empty() {
        return None;
    }
    let mut value: i64 = digits.parse().ok()?;
    if (norm.contains("mil") || norm.split_whitespace().any(|word| word == "k")) && value < 10_000
    {
        value *= 1000;
    }
    Some(value)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn commands_ignore_accents_and_slash() {
        assert_eq!(global_command("/Ajuda"), Some(GlobalCommand::Help));
        assert_eq!(global_command("Olá"), Some(GlobalCommand::Menu));
        assert_eq!(global_command("novo alerta"), Some(GlobalCommand::NewAlert));
        assert_eq!(global_command("1"), None);
    }

    #[test]
    fn money_understands_mil() {
        assert_eq!(parse_money("400 mil"), Some(400_000));
        assert_eq!(parse_money("2.500"), Some(2500));
        assert_eq!(parse_money("abc"), None);
    }
}
