use serde_json::Value;

pub fn format_brl(value: Option<i64>) -> String {
    let Some(value) = value else {
        return "—".to_string();
    };
    let negative = value < 0;
    let abs = value.unsigned_abs();
    let mut grouped = String::new();
    let raw = abs.to_string();
    for (index, ch) in raw.chars().rev().enumerate() {
        if index > 0 && index % 3 == 0 {
            grouped.push('.');
        }
        grouped.push(ch);
    }
    let grouped: String = grouped.chars().rev().collect();
    let sign = if negative { "-" } else { "" };
    format!("{sign}R$ {grouped},00")
}

pub fn fee_amount(value: &Value) -> i64 {
    let amount = match value {
        Value::Bool(_) | Value::Null => return 0,
        Value::Number(number) => number.as_i64().unwrap_or(0),
        Value::String(raw) => money_to_int(raw).unwrap_or(0),
        _ => return 0,
    };
    if amount > 0 {
        amount
    } else {
        0
    }
}

pub fn money_to_int(value: &str) -> Option<i64> {
    let digits: String = value.chars().filter(|ch| ch.is_ascii_digit()).collect();
    if digits.is_empty() {
        None
    } else {
        digits.parse().ok()
    }
}

pub fn json_fee(properties: &Value, key: &str) -> i64 {
    properties.get(key).map(fee_amount).unwrap_or(0)
}

pub fn json_int(properties: &Value, key: &str) -> Option<i64> {
    match properties.get(key)? {
        Value::Number(number) => number
            .as_i64()
            .or_else(|| number.as_f64().map(|value| value as i64)),
        Value::String(raw) => raw.parse().ok().or_else(|| money_to_int(raw)),
        _ => None,
    }
}

pub fn effective_listing_price(
    price_value: Option<i64>,
    listing_kind: &str,
    condominio: i64,
    iptu: i64,
) -> Option<i64> {
    let price = price_value?;
    if listing_kind != "aluguel" {
        return Some(price);
    }
    Some(price + condominio.max(0) + iptu.max(0))
}

pub fn format_listing_price(
    price_value: Option<i64>,
    listing_kind: &str,
    condominio: i64,
    iptu: i64,
) -> String {
    let total = effective_listing_price(price_value, listing_kind, condominio, iptu);
    if price_value.is_none() || listing_kind != "aluguel" || (condominio == 0 && iptu == 0) {
        return format_brl(total);
    }
    let mut parts = vec![format!("aluguel {}", format_brl(price_value))];
    if condominio > 0 {
        parts.push(format!("cond. {}", format_brl(Some(condominio))));
    }
    if iptu > 0 {
        parts.push(format!("IPTU {}", format_brl(Some(iptu))));
    }
    format!("{} ({})", format_brl(total), parts.join(" + "))
}

pub fn format_k(value: i64) -> String {
    if value >= 1_000_000 {
        let scaled = value as f64 / 1_000_000.0;
        let text = format!("{scaled:.1}").replace('.', ",");
        let text = text.trim_end_matches(",0");
        return format!("{text}M");
    }
    if value >= 1000 && value % 1000 == 0 {
        return format!("{} mil", value / 1000);
    }
    let raw = value.to_string();
    let mut grouped = String::new();
    for (index, ch) in raw.chars().rev().enumerate() {
        if index > 0 && index % 3 == 0 {
            grouped.push('.');
        }
        grouped.push(ch);
    }
    grouped.chars().rev().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formats_reais() {
        assert_eq!(format_brl(Some(13000)), "R$ 13.000,00");
        assert_eq!(format_brl(Some(800)), "R$ 800,00");
        assert_eq!(format_brl(None), "—");
    }

    #[test]
    fn rent_adds_fees() {
        assert_eq!(
            effective_listing_price(Some(1000), "aluguel", 200, 50),
            Some(1250)
        );
        assert_eq!(
            effective_listing_price(Some(1000), "venda", 200, 50),
            Some(1000)
        );
    }
}
