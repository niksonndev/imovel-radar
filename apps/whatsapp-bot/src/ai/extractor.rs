use std::collections::HashMap;

use regex::Regex;
use serde::Deserialize;
use serde_json::json;
use unicode_normalization::UnicodeNormalization;

use crate::config::Config;

#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
pub struct ExtractedAlert {
    pub municipality: Option<String>,
    pub listing_kind: Option<String>,
    pub categories: Option<Vec<String>>,
    pub min_price: Option<i64>,
    pub max_price: Option<i64>,
    pub min_rooms: Option<i32>,
    pub neighbourhoods: Option<Vec<String>>,
}

const SYSTEM_PROMPT: &str = "\
Você é o extrator de intenções do Imóvel Radar (bot de alertas imobiliários).
Sua missão é extrair do texto do usuário os critérios de busca em JSON estruturado.

Regras de negócio:
1. Cidades suportadas: 'Maceió', 'Recife' e 'Natal'. Se o usuário não citar a cidade mas citar
   um bairro famoso (ex: Ponta Verde/Jatiúca/Pajuçara -> Maceió; Boa Viagem/Pina/Graças -> Recife;
   Ponta Negra/Tirol/Petrópolis -> Natal), infira a cidade. 'mcz' = Maceió. Se desconhecida, null.
2. Tipo de transação (listing_kind): 'aluguel' ou 'venda'. Se não estiver explícito:
   - Se o preço máximo for <= 20.000, infira 'aluguel'.
   - Se o preço máximo ou mínimo for >= 50.000, infira 'venda'.
   - Entre 20.000 e 50.000 ou sem preço, deixe null.
3. Categorias: apenas 'Apartamentos', 'Casas', 'Aluguel de quartos'.
   - kitnet, loft, flat, studio, ap, apê, apartamento -> 'Apartamentos'.
   - Se o usuário não especificar tipo, deixe categories = null.
4. Preço: converta expressões como '400k' -> 400000, '400 mil' -> 400000, '2.500' -> 2500,
   '3 mil' -> 3000. 'até 400 mil' significa max_price = 400000 e min_price = null.
5. Quartos: '2 quartos', '2 dorms', '2 qts', '2+' -> min_rooms = 2.
6. Bairros: extraia os nomes dos bairros citados.
   Reconheça 'PV' -> 'Ponta Verde', 'BV' -> 'Boa Viagem'.
";

fn extraction_schema() -> serde_json::Value {
    json!({
        "name": "alert_extraction",
        "strict": true,
        "schema": {
            "type": "object",
            "properties": {
                "municipality": {
                    "anyOf": [
                        {"type": "string", "enum": ["Maceió", "Recife", "Natal"]},
                        {"type": "null"}
                    ]
                },
                "listing_kind": {
                    "anyOf": [
                        {"type": "string", "enum": ["aluguel", "venda"]},
                        {"type": "null"}
                    ]
                },
                "categories": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["Apartamentos", "Casas", "Aluguel de quartos"]
                            }
                        },
                        {"type": "null"}
                    ]
                },
                "min_price": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                "max_price": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                "min_rooms": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                "neighbourhoods": {
                    "anyOf": [
                        {"type": "array", "items": {"type": "string"}},
                        {"type": "null"}
                    ]
                }
            },
            "required": [
                "municipality", "listing_kind", "categories", "min_price",
                "max_price", "min_rooms", "neighbourhoods"
            ],
            "additionalProperties": false
        }
    })
}

pub fn normalize_name(name: &str) -> String {
    name.nfkd()
        .filter(|ch| !unicode_normalization::char::is_combining_mark(*ch))
        .collect::<String>()
        .trim()
        .to_lowercase()
}

fn synonyms() -> HashMap<&'static str, &'static str> {
    HashMap::from([("pv", "ponta verde"), ("bv", "boa viagem")])
}

fn levenshtein(left: &str, right: &str) -> usize {
    let a: Vec<char> = left.chars().collect();
    let b: Vec<char> = right.chars().collect();
    if a.is_empty() {
        return b.len();
    }
    if b.is_empty() {
        return a.len();
    }
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    let mut curr = vec![0; b.len() + 1];
    for (i, ca) in a.iter().enumerate() {
        curr[0] = i + 1;
        for (j, cb) in b.iter().enumerate() {
            let cost = if ca == cb { 0 } else { 1 };
            curr[j + 1] = (prev[j + 1] + 1).min(curr[j] + 1).min(prev[j] + cost);
        }
        std::mem::swap(&mut prev, &mut curr);
    }
    prev[b.len()]
}

fn similarity(left: &str, right: &str) -> f64 {
    if left == right {
        return 1.0;
    }
    let max_len = left.chars().count().max(right.chars().count());
    if max_len == 0 {
        return 1.0;
    }
    1.0 - (levenshtein(left, right) as f64 / max_len as f64)
}

pub fn match_neighbourhoods(raw: Option<&[String]>, available: &[String]) -> Vec<String> {
    let Some(raw) = raw else {
        return Vec::new();
    };
    if raw.is_empty() || available.is_empty() {
        return Vec::new();
    }
    let synonyms = synonyms();
    let pairs: Vec<(String, String)> = available
        .iter()
        .map(|name| (normalize_name(name), name.clone()))
        .collect();
    let mut matched = Vec::new();
    for item in raw {
        let clean = item.trim();
        if clean.is_empty() {
            continue;
        }
        let mut norm = normalize_name(clean);
        if let Some(mapped) = synonyms.get(norm.as_str()) {
            norm = (*mapped).to_string();
        }
        if let Some((_, canon)) = pairs.iter().find(|(key, _)| key == &norm) {
            if !matched.contains(canon) {
                matched.push(canon.clone());
            }
            continue;
        }
        let mut best: Option<(f64, String)> = None;
        for (key, canon) in &pairs {
            let score = similarity(&norm, key);
            if score >= 0.8 && best.as_ref().map(|(current, _)| score > *current).unwrap_or(true)
            {
                best = Some((score, canon.clone()));
            }
        }
        if let Some((_, canon)) = best {
            if !matched.contains(&canon) {
                matched.push(canon);
            }
        }
    }
    matched
}

fn known_neighbourhoods() -> Vec<(&'static str, &'static str)> {
    vec![
        ("ponta verde", "Maceió"),
        ("pv", "Maceió"),
        ("jatiuca", "Maceió"),
        ("pajucara", "Maceió"),
        ("mangabeiras", "Maceió"),
        ("cruz das almas", "Maceió"),
        ("farol", "Maceió"),
        ("serraria", "Maceió"),
        ("antares", "Maceió"),
        ("tabuleiro", "Maceió"),
        ("gruta", "Maceió"),
        ("jacarecica", "Maceió"),
        ("centro maceio", "Maceió"),
        ("boa viagem", "Recife"),
        ("bv", "Recife"),
        ("pina", "Recife"),
        ("gracas", "Recife"),
        ("espinheiro", "Recife"),
        ("madalena", "Recife"),
        ("casa forte", "Recife"),
        ("setubal", "Recife"),
        ("jaqueira", "Recife"),
        ("derby", "Recife"),
        ("ponta negra", "Natal"),
        ("tirol", "Natal"),
        ("petropolis", "Natal"),
        ("candelaria", "Natal"),
        ("capim macio", "Natal"),
        ("lagoa nova", "Natal"),
    ]
}

fn title_case(value: &str) -> String {
    value
        .split_whitespace()
        .map(|word| {
            let mut chars = word.chars();
            match chars.next() {
                None => String::new(),
                Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn parse_amount(raw: &str) -> Option<f64> {
    let normalized = raw.replace('.', "").replace(',', ".");
    normalized.parse().ok()
}

pub fn mock_extract_alert(text: &str) -> ExtractedAlert {
    let norm = normalize_name(text);
    let city_re = Regex::new(r"\b(maceio|mcz|alagoas)\b").unwrap();
    let recife_re = Regex::new(r"\b(recife|pe|pernambuco)\b").unwrap();
    let natal_re = Regex::new(r"\b(natal|rn|rio grande do norte)\b").unwrap();
    let mut city = if city_re.is_match(&norm) {
        Some("Maceió".to_string())
    } else if recife_re.is_match(&norm) {
        Some("Recife".to_string())
    } else if natal_re.is_match(&norm) {
        Some("Natal".to_string())
    } else {
        None
    };

    let synonyms = synonyms();
    let mut detected = Vec::new();
    let mut known = known_neighbourhoods();
    known.sort_by_key(|(name, _)| std::cmp::Reverse(name.len()));
    for (name, nb_city) in known {
        let pattern = format!(r"\b{}\b", regex::escape(name));
        let re = Regex::new(&pattern).unwrap();
        if re.is_match(&norm) {
            let canon = synonyms.get(name).copied().unwrap_or(name);
            let titled = title_case(canon);
            if !detected.contains(&titled) {
                detected.push(titled);
            }
            if city.is_none() {
                city = Some(nb_city.to_string());
            }
        }
    }

    let rent_re = Regex::new(r"\b(aluguel|alugar|locacao|alugo|aluga)\b").unwrap();
    let sale_re = Regex::new(r"\b(comprar|compra|venda|compro)\b").unwrap();
    let mut kind = if rent_re.is_match(&norm) {
        Some("aluguel".to_string())
    } else if sale_re.is_match(&norm) {
        Some("venda".to_string())
    } else {
        None
    };

    let apt_re = Regex::new(r"\b(ap|ape|apto|apartamento|apartamentos|flat|studio|kitnet|loft)\b").unwrap();
    let house_re = Regex::new(r"\b(casa|casas|sobrado)\b").unwrap();
    let room_re = Regex::new(r"\b(quarto|quartos para alugar)\b").unwrap();
    let rooms_count_re = Regex::new(r"\d+\s*quartos").unwrap();
    let categories = if apt_re.is_match(&norm) {
        Some(vec!["Apartamentos".to_string()])
    } else if house_re.is_match(&norm) {
        Some(vec!["Casas".to_string()])
    } else if room_re.is_match(&norm) && !rooms_count_re.is_match(&norm) {
        Some(vec!["Aluguel de quartos".to_string()])
    } else {
        None
    };

    let range_re = Regex::new(
        r"(?:entre|de)\s*(\d+[\.,]?\d*)\s*(mil|k)?\s*(?:e|a|ate)\s*(\d+[\.,]?\d*)\s*(mil|k)?",
    )
    .unwrap();
    let mut min_price = None;
    let mut max_price = None;
    if let Some(caps) = range_re.captures(&norm) {
        let p1_raw = caps.get(1).map(|m| m.as_str()).unwrap_or("0");
        let p1_unit = caps.get(2).map(|m| m.as_str());
        let p2_raw = caps.get(3).map(|m| m.as_str()).unwrap_or("0");
        let p2_unit = caps.get(4).map(|m| m.as_str());
        let mut p1 = parse_amount(p1_raw).unwrap_or(0.0);
        let mut p2 = parse_amount(p2_raw).unwrap_or(0.0);
        if p1_unit.is_some() || (p2_unit.is_some() && p1 < 1000.0) {
            p1 *= 1000.0;
        }
        if p2_unit.is_some() {
            p2 *= 1000.0;
        }
        min_price = Some(p1 as i64);
        max_price = Some(p2 as i64);
    } else {
        let max_re = Regex::new(
            r"(?:ate|no maximo|no max|maximo de|no valor de|por ate)?\s*(?:r\$)?\s*(\d+[\.,]?\d*)\s*(mil|k)?\b",
        )
        .unwrap();
        if let Some(caps) = max_re.captures(&norm) {
            if let Some(raw) = caps.get(1).map(|m| m.as_str()) {
                if let Some(mut val) = parse_amount(raw) {
                    let unit = caps.get(2).map(|m| m.as_str());
                    if unit.is_some() || (val < 200.0 && (norm.contains("mil") || norm.contains('k')))
                    {
                        val *= 1000.0;
                    }
                    if val >= 300.0 {
                        max_price = Some(val as i64);
                    }
                }
            }
        }
    }

    if kind.is_none() {
        if let Some(max_price) = max_price {
            if max_price <= 20_000 {
                kind = Some("aluguel".to_string());
            } else if max_price >= 50_000 {
                kind = Some("venda".to_string());
            }
        }
    }

    let rooms_re =
        Regex::new(r"(\d+)\s*(?:\+|mais)?\s*(?:quartos?|dorms?|dormitorios?|qts?)\b").unwrap();
    let min_rooms = rooms_re
        .captures(&norm)
        .and_then(|caps| caps.get(1))
        .and_then(|m| m.as_str().parse().ok());

    ExtractedAlert {
        municipality: city,
        listing_kind: kind,
        categories,
        min_price,
        max_price,
        min_rooms,
        neighbourhoods: if detected.is_empty() {
            None
        } else {
            Some(detected)
        },
    }
}

pub async fn extract_alert_intent(
    http: &reqwest::Client,
    cfg: &Config,
    text: &str,
) -> Option<ExtractedAlert> {
    let cleaned = text.trim();
    if cleaned.is_empty() {
        return None;
    }
    if cfg.llm_provider == "openai" && !cfg.openai_api_key.is_empty() {
        match extract_with_openai(http, cfg, cleaned).await {
            Ok(Some(extracted)) => return Some(extracted),
            Ok(None) => tracing::info!("extração OpenAI vazia; usando mock"),
            Err(error) => tracing::warn!(%error, "falha na OpenAI; usando mock"),
        }
    }
    Some(mock_extract_alert(cleaned))
}

async fn extract_with_openai(
    http: &reqwest::Client,
    cfg: &Config,
    text: &str,
) -> anyhow::Result<Option<ExtractedAlert>> {
    let payload = json!({
        "model": cfg.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": extraction_schema()
        },
        "temperature": 0.0
    });
    let response = http
        .post("https://api.openai.com/v1/chat/completions")
        .bearer_auth(&cfg.openai_api_key)
        .json(&payload)
        .timeout(cfg.llm_timeout)
        .send()
        .await?;
    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        tracing::warn!(%status, body = %body.chars().take(300).collect::<String>(), "openai");
        return Ok(None);
    }
    let data: serde_json::Value = response.json().await?;
    let content = data["choices"][0]["message"]["content"]
        .as_str()
        .unwrap_or("");
    if content.is_empty() {
        return Ok(None);
    }
    Ok(Some(serde_json::from_str(content)?))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mock_extract_maceio_sale_apartment() {
        let res = mock_extract_alert("Apartamento até 400 mil perto da Ponta Verde");
        assert_eq!(res.municipality.as_deref(), Some("Maceió"));
        assert_eq!(res.listing_kind.as_deref(), Some("venda"));
        assert_eq!(
            res.categories,
            Some(vec!["Apartamentos".to_string()])
        );
        assert_eq!(res.max_price, Some(400_000));
        assert_eq!(res.min_price, None);
        let matched = match_neighbourhoods(
            res.neighbourhoods.as_deref(),
            &["Ponta Verde".into(), "Jatiúca".into(), "Pajuçara".into()],
        );
        assert_eq!(matched, vec!["Ponta Verde".to_string()]);
    }

    #[test]
    fn mock_extract_recife_rent_kitnet() {
        let res = mock_extract_alert("aluguel kitnet Boa Viagem até 2.500");
        assert_eq!(res.municipality.as_deref(), Some("Recife"));
        assert_eq!(res.listing_kind.as_deref(), Some("aluguel"));
        assert_eq!(
            res.categories,
            Some(vec!["Apartamentos".to_string()])
        );
        assert_eq!(res.max_price, Some(2500));
        let matched = match_neighbourhoods(
            res.neighbourhoods.as_deref(),
            &["Boa Viagem".into(), "Pina".into()],
        );
        assert_eq!(matched, vec!["Boa Viagem".to_string()]);
    }

    #[test]
    fn mock_extract_natal_sale_house() {
        let res = mock_extract_alert("casa em Natal até 500 mil com 3 quartos");
        assert_eq!(res.municipality.as_deref(), Some("Natal"));
        assert_eq!(res.listing_kind.as_deref(), Some("venda"));
        assert_eq!(res.categories, Some(vec!["Casas".to_string()]));
        assert_eq!(res.max_price, Some(500_000));
        assert_eq!(res.min_rooms, Some(3));
    }

    #[test]
    fn match_neighbourhoods_synonyms_and_fuzzy() {
        let available = vec![
            "Ponta Verde".into(),
            "Jatiúca".into(),
            "Boa Viagem".into(),
            "Ponta Negra".into(),
        ];
        assert_eq!(
            match_neighbourhoods(Some(&["PV".into()]), &available),
            vec!["Ponta Verde".to_string()]
        );
        assert_eq!(
            match_neighbourhoods(Some(&["BV".into()]), &available),
            vec!["Boa Viagem".to_string()]
        );
        assert_eq!(
            match_neighbourhoods(Some(&["jatiuca".into()]), &available),
            vec!["Jatiúca".to_string()]
        );
        assert_eq!(
            match_neighbourhoods(Some(&["ponta negra".into()]), &available),
            vec!["Ponta Negra".to_string()]
        );
        assert!(match_neighbourhoods(Some(&["Bairro Fantasma".into()]), &available).is_empty());
        assert!(match_neighbourhoods(Some(&[]), &available).is_empty());
        assert!(match_neighbourhoods(None, &available).is_empty());
        assert!(match_neighbourhoods(Some(&["PV".into()]), &[]).is_empty());
    }
}
