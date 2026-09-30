use serde::{Deserialize, Serialize};
use serde_json::Value;
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
    AssistantConversation,
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
    AssistantRemoveChoice { ids: Vec<i32> },
    AssistantDeleteConfirm { id: i32 },
    DeleteAccountConfirm,
    Deleted,
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
    #[serde(default)]
    pub assistant_history: Vec<Value>,
    #[serde(default)]
    pub assistant_history_updated_at: Option<i64>,
}

impl Session {
    pub fn menu() -> Self {
        Self {
            step: Step::Menu,
            draft: Draft::default(),
            assistant_history: Vec::new(),
            assistant_history_updated_at: None,
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
    Privacy,
    DeleteData,
    Support,
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
        "privacidade" | "politica de privacidade" | "termos" => Some(GlobalCommand::Privacy),
        "excluir dados" | "excluir_dados" | "apagar meus dados" => Some(GlobalCommand::DeleteData),
        "suporte" | "atendimento" => Some(GlobalCommand::Support),
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
    if !digits.is_empty() {
        let mut value: i64 = digits.parse().ok()?;
        if (norm.contains("mil") || norm.split_whitespace().any(|word| word == "k"))
            && value < 10_000
        {
            value *= 1000;
        }
        return Some(value);
    }
    parse_number_words(text)
}

/// Converte números por extenso/compostos em pt-BR em inteiro.
/// Entende unidades, dezenas, centenas, milhares e milhões, inclusive compostos
/// como "mil e quinhentos" (1500), "dois mil" (2000) ou "trezentos mil" (300000).
/// Serve para interpretar áudios transcritos nos passos de preço/quartos do wizard.
pub fn parse_number_words(text: &str) -> Option<i64> {
    use std::collections::HashMap;
    let words: HashMap<&str, i64> = [
        ("um", 1),
        ("uma", 1),
        ("dois", 2),
        ("duas", 2),
        ("tres", 3),
        ("quatro", 4),
        ("cinco", 5),
        ("seis", 6),
        ("sete", 7),
        ("oito", 8),
        ("nove", 9),
        ("dez", 10),
        ("onze", 11),
        ("doze", 12),
        ("treze", 13),
        ("quatorze", 14),
        ("catorze", 14),
        ("quinze", 15),
        ("dezesseis", 16),
        ("dezessete", 17),
        ("dezoito", 18),
        ("dezenove", 19),
        ("vinte", 20),
        ("trinta", 30),
        ("quarenta", 40),
        ("cinquenta", 50),
        ("sessenta", 60),
        ("setenta", 70),
        ("oitenta", 80),
        ("noventa", 90),
        ("cem", 100),
        ("cento", 100),
        ("duzentos", 200),
        ("duzentas", 200),
        ("trezentos", 300),
        ("trezentas", 300),
        ("quatrocentos", 400),
        ("quatrocentas", 400),
        ("quinhentos", 500),
        ("quinhentas", 500),
        ("seiscentos", 600),
        ("seiscentas", 600),
        ("setecentos", 700),
        ("setecentas", 700),
        ("oitocentos", 800),
        ("oitocentas", 800),
        ("novecentos", 900),
        ("novecentas", 900),
    ]
    .iter()
    .copied()
    .collect();
    let multiples: HashMap<&str, i64> = [
        ("mil", 1_000),
        ("milhao", 1_000_000),
        ("milhoes", 1_000_000),
    ]
    .iter()
    .copied()
    .collect();

    let mut total: i64 = 0;
    let mut current: i64 = 0;
    let mut seen_any = false;
    for token in normalize_text(text).split_whitespace() {
        if matches!(token, "e" | "de" | "reais" | "real" | "ao" | "a" | "por" | "mes" | "mês") {
            continue;
        }
        if let Some(&mult) = multiples.get(token) {
            current = current.max(1) * mult;
            total += current;
            current = 0;
            seen_any = true;
        } else if let Some(&value) = words.get(token) {
            current += value;
            seen_any = true;
        }
    }
    if seen_any {
        Some(total + current)
    } else {
        None
    }
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
        assert_eq!(parse_money("até dois mil"), Some(2000));
        assert_eq!(parse_money("mil e quinhentos"), Some(1500));
        assert_eq!(parse_money("trezentos mil reais"), Some(300_000));
        assert_eq!(parse_money("cento e vinte"), Some(120));
    }

    #[test]
    fn number_words_parse_compounds() {
        assert_eq!(parse_number_words("dois mil"), Some(2000));
        assert_eq!(parse_number_words("dois mil e duzentos e cinquenta"), Some(2250));
        assert_eq!(parse_number_words("setecentos mil"), Some(700_000));
        assert_eq!(parse_number_words("um milhao"), Some(1_000_000));
        assert_eq!(parse_number_words("abc"), None);
    }

    #[test]
    fn privacy_and_support_commands_are_global() {
        assert_eq!(global_command("/privacidade"), Some(GlobalCommand::Privacy));
        assert_eq!(global_command("excluir dados"), Some(GlobalCommand::DeleteData));
        assert_eq!(global_command("suporte"), Some(GlobalCommand::Support));
    }

    #[test]
    fn assistant_session_roundtrips_short_history() {
        let mut session = Session::menu();
        session.step = Step::AssistantConversation;
        session.assistant_history = vec![serde_json::json!({
            "role": "user",
            "content": "Maceió"
        })];
        session.assistant_history_updated_at = Some(1_800_000_000);
        let encoded = serde_json::to_value(&session).unwrap();
        let decoded: Session = serde_json::from_value(encoded).unwrap();
        assert_eq!(decoded, session);
    }
}
