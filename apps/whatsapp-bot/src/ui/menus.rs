use chrono::{DateTime, Utc};

use crate::config::Config;
use crate::models::{Alert, Listing};
use crate::money::{format_brl, format_k, format_listing_price, json_fee, json_int};
use crate::session::Draft;

pub struct Preset {
    pub label: &'static str,
    pub min: i64,
    pub max: i64,
}

pub fn price_presets(listing_kind: &str, municipality: &str) -> Vec<Preset> {
    if municipality == "Recife" && listing_kind == "venda" {
        vec![
            Preset { label: "Até R$ 350 mil", min: 0, max: 350_000 },
            Preset { label: "R$ 350 – 600 mil", min: 350_000, max: 600_000 },
            Preset { label: "R$ 600 mil – 1,2 mi", min: 600_000, max: 1_200_000 },
            Preset { label: "R$ 1,2 mi+", min: 1_200_000, max: 99_999_999 },
        ]
    } else if municipality == "Recife" {
        vec![
            Preset { label: "Até R$ 2.500", min: 0, max: 2_500 },
            Preset { label: "R$ 2.500 – R$ 4.000", min: 2_500, max: 4_000 },
            Preset { label: "R$ 4.000 – R$ 7.000", min: 4_000, max: 7_000 },
            Preset { label: "R$ 7.000+", min: 7_000, max: 999_999 },
        ]
    } else if listing_kind == "venda" {
        vec![
            Preset { label: "Até R$ 150 mil", min: 0, max: 150_000 },
            Preset { label: "R$ 150 – 300 mil", min: 150_000, max: 300_000 },
            Preset { label: "R$ 300 – 500 mil", min: 300_000, max: 500_000 },
            Preset { label: "R$ 500 mil+", min: 500_000, max: 99_999_999 },
        ]
    } else {
        vec![
            Preset { label: "Até R$ 800", min: 0, max: 800 },
            Preset { label: "R$ 800 – R$ 1.500", min: 800, max: 1_500 },
            Preset { label: "R$ 1.500 – R$ 3.000", min: 1_500, max: 3_000 },
            Preset { label: "R$ 3.000+", min: 3_000, max: 999_999 },
        ]
    }
}

pub fn category_options(listing_kind: &str) -> Vec<(&'static str, &'static str)> {
    if listing_kind == "venda" {
        vec![("Apartamentos", "Apartamento"), ("Casas", "Casa")]
    } else {
        vec![
            ("Apartamentos", "Apartamento"),
            ("Casas", "Casa"),
            ("Aluguel de quartos", "Quarto"),
        ]
    }
}

pub fn main_menu() -> String {
    "\
👋 *Olá!* Sou o bot de alertas OLX — *Maceió, Recife e Natal*.

🏠 *Menu principal*
1. Novo alerta
2. Meus alertas
3. Acompanhando
4. Ajuda
5. Radar Pro

Responda com o número."
        .to_string()
}

pub fn help_text() -> String {
    "\
*Comandos*
menu — menu principal
novo alerta — criar alerta
meus alertas — listar e apagar
acompanhando — anúncios que você segue
pro — trial Radar Pro por e-mail
cancelar — sai do que estiver fazendo
ajuda — esta mensagem"
        .to_string()
}

pub fn intent_prompt() -> String {
    "\
🆕 *Novo alerta*

💬 *Que imóvel você procura?*

Me diga em uma frase, por exemplo:
_\"Apartamento até 400 mil perto da Ponta Verde\"_
_\"Aluguel kitnet em Boa Viagem até 2.500\"_

Ou responda *1* para escolher passo a passo."
        .to_string()
}

pub fn city_prompt() -> String {
    "🆕 *Novo alerta*\n\nEm qual cidade?\n1. Maceió\n2. Recife\n3. Natal".to_string()
}

pub fn kind_prompt() -> String {
    "🏷️ *Você quer alugar ou comprar?*\n1. Alugar\n2. Comprar".to_string()
}

pub fn categories_prompt(listing_kind: &str, selected: &[String]) -> String {
    let options = category_options(listing_kind);
    let mut lines = vec!["🏠 *Tipo de imóvel*".to_string(), String::new()];
    lines.push("Marque um ou mais. Sem seleção = qualquer tipo.".to_string());
    for (index, (_, label)) in options.iter().enumerate() {
        let value = options[index].0;
        let mark = if selected.iter().any(|item| item == value) {
            "✅"
        } else {
            "▫️"
        };
        lines.push(format!("{}. {mark} {label}", index + 1));
    }
    let chosen = categories_label(selected);
    lines.push(String::new());
    lines.push(format!("*Selecionados:* {chosen}"));
    lines.push("Responda com os números (ex: `1,2`) ou *0* para concluir.".to_string());
    lines.join("\n")
}

pub fn price_prompt(listing_kind: &str, municipality: &str) -> String {
    let label = if listing_kind == "venda" { "compra" } else { "aluguel" };
    let mut lines = vec![format!("💰 *Faixa de preço ({label})*")];
    if listing_kind != "venda" {
        lines.push(String::new());
        lines.push("Condomínio e IPTU entram na conta.".to_string());
    }
    lines.push(String::new());
    for (index, preset) in price_presets(listing_kind, municipality).iter().enumerate() {
        lines.push(format!("{}. {}", index + 1, preset.label));
    }
    lines.push("5. Personalizado".to_string());
    lines.join("\n")
}

pub fn price_min_prompt() -> String {
    "Personalizado: envie o *preço mínimo* em R$ (só o número).".to_string()
}

pub fn price_max_prompt() -> String {
    "Preço *máximo* (R$):".to_string()
}

pub fn rooms_prompt() -> String {
    "\
🛏 *Quartos*

Mínimo de quartos?
1. Qualquer
2. 1+
3. 2+
4. 3+
5. 4+"
        .to_string()
}

pub fn neighbourhoods_prompt(all: &[String], page: usize, selected: &[String]) -> String {
    const PAGE: usize = 8;
    if all.is_empty() {
        return "\
📍 *Bairros*

Ainda não há bairros desta cidade no radar.
Responda *0* para valer para *qualquer bairro*."
            .to_string();
    }
    let pages = all.len().div_ceil(PAGE).max(1);
    let page = page.min(pages - 1);
    let start = page * PAGE;
    let end = (start + PAGE).min(all.len());
    let mut lines = vec![format!("📍 *Bairros* (página {}/{pages})", page + 1)];
    let chosen = if selected.is_empty() {
        "nenhum ainda".to_string()
    } else {
        selected.join(", ")
    };
    lines.push(format!("*Selecionados:* {chosen}"));
    lines.push(String::new());
    for (offset, name) in all[start..end].iter().enumerate() {
        let mark = if selected.iter().any(|item| item == name) {
            "✅"
        } else {
            "▫️"
        };
        lines.push(format!("{}. {mark} {name}", offset + 1));
    }
    lines.push(String::new());
    lines.push("Números marcam ou desmarcam (ex: `1,3`).".to_string());
    lines.push("*mais* próxima · *voltar* anterior · *0* concluir.".to_string());
    lines.join("\n")
}

pub fn name_prompt(suggestion: &str) -> String {
    format!(
        "📝 *Nome do alerta*\n\nSugestão: _{suggestion}_\n\nEnvie um nome ou *1* para usar a sugestão."
    )
}

pub fn confirm_prompt(draft: &Draft) -> String {
    let city = draft.municipality.as_deref().unwrap_or("Maceió");
    let kind = kind_label(draft.listing_kind.as_deref());
    let price = price_range_label(draft.min_price, draft.max_price);
    let rooms = rooms_label(draft.min_rooms);
    let cats = categories_label(&draft.categories);
    let nb = if draft.neighbourhoods.is_empty() {
        "Qualquer bairro".to_string()
    } else {
        let mut names = draft.neighbourhoods.clone();
        names.sort();
        names.join(", ")
    };
    let name = draft.alert_name.as_deref().unwrap_or("—");
    format!(
        "\
🧾 *Confirmação do alerta*

📍 *Cidade:* {city}
🏷️ *Tipo:* {kind}
💰 *Preço:* {price}
🛏 *Quartos:* {rooms}
🏠 *Categoria:* {cats}
📍 *Bairros:* {nb}
📝 *Nome:* {name}

1. Confirmar
2. Cancelar"
    )
}

pub fn kind_label(kind: Option<&str>) -> &'static str {
    if kind == Some("venda") {
        "Comprar"
    } else {
        "Alugar"
    }
}

pub fn rooms_label(min_rooms: Option<i32>) -> String {
    match min_rooms {
        None => "qualquer".to_string(),
        Some(rooms) => format!("{rooms}+"),
    }
}

pub fn categories_label(categories: &[String]) -> String {
    if categories.is_empty() {
        return "qualquer".to_string();
    }
    categories
        .iter()
        .map(|category| match category.as_str() {
            "Apartamentos" => "Apartamento",
            "Casas" => "Casa",
            "Aluguel de quartos" => "Quarto",
            other => other,
        })
        .collect::<Vec<_>>()
        .join(", ")
}

pub fn price_range_label(min_price: Option<i64>, max_price: Option<i64>) -> String {
    match (min_price, max_price) {
        (None, max_price) => format!("Até {}", format_brl(max_price)),
        (Some(min_price), None) => format!("A partir de {}", format_brl(Some(min_price))),
        (Some(min_price), Some(max_price)) => {
            format!("{} – {}", format_brl(Some(min_price)), format_brl(Some(max_price)))
        }
    }
}

pub fn auto_alert_name(draft: &Draft) -> String {
    let cat_label = match draft.categories.as_slice() {
        [only] if only == "Apartamentos" => "Apto",
        [only] if only == "Casas" => "Casa",
        [only] if only == "Aluguel de quartos" => "Quarto",
        [only] => only.as_str(),
        _ => "Imóvel",
    };
    let loc_label = match draft.neighbourhoods.as_slice() {
        [one] => one.clone(),
        [first, second] => format!("{first} e {second}"),
        [first, rest @ ..] if !rest.is_empty() => format!("{first} e +{}", rest.len()),
        _ => draft
            .municipality
            .clone()
            .unwrap_or_else(|| "Maceió".to_string()),
    };
    let price_label = match (draft.min_price, draft.max_price) {
        (Some(min_price), Some(max_price)) if min_price > 0 => {
            format!("R$ {}–{}", format_k(min_price), format_k(max_price))
        }
        (_, Some(max_price)) => format!("até R$ {}", format_k(max_price)),
        (Some(min_price), None) => format!("a partir de R$ {}", format_k(min_price)),
        _ => String::new(),
    };
    let parts = [cat_label.to_string(), loc_label, price_label]
        .into_iter()
        .filter(|part| !part.is_empty())
        .collect::<Vec<_>>();
    let name = parts.join(" · ");
    name.chars().take(120).collect()
}

pub fn alerts_list(alerts: &[Alert]) -> String {
    if alerts.is_empty() {
        return "📋 *Meus alertas*\n\nVocê ainda não tem alertas.\n\n1. Novo alerta\n2. Menu"
            .to_string();
    }
    let mut lines = vec!["📋 *Meus alertas*".to_string(), String::new()];
    for (index, alert) in alerts.iter().enumerate() {
        let name = alert.alert_name.as_deref().unwrap_or("Sem nome");
        let status = if alert.active { "✅" } else { "⏸" };
        lines.push(format!(
            "{}. {status} {name} · {} · {}",
            index + 1,
            alert.municipality,
            kind_label(Some(&alert.listing_kind))
        ));
    }
    lines.push(String::new());
    lines.push("Responda com o número para ver o alerta, ou *menu*.".to_string());
    lines.join("\n")
}

pub fn alert_detail(alert: &Alert) -> String {
    let name = alert.alert_name.as_deref().unwrap_or("Sem nome");
    let status = if alert.active {
        "✅ Alerta ativo"
    } else {
        "❌ Alerta inativo"
    };
    let nb = if alert.neighbourhoods.is_empty() {
        "Todos".to_string()
    } else {
        alert.neighbourhoods.join(", ")
    };
    let created = alert
        .created_at
        .map(|value| value.format("%d/%m/%Y").to_string())
        .unwrap_or_else(|| "—".to_string());
    format!(
        "\
📋 *Meus alertas*

*{name}*
{status}
📍 {}
🏷️ {}
💰 {}
🛏 {}
🏠 {}
📍 {nb}
📅 *Criado:* {created}

1. Apagar
2. Editar
3. Voltar",
        alert.municipality,
        kind_label(Some(&alert.listing_kind)),
        price_range_label(
            alert.min_price.map(i64::from),
            alert.max_price.map(i64::from)
        ),
        rooms_label(alert.min_rooms),
        categories_label(&alert.categories),
    )
}

pub fn edit_stub(name: &str) -> String {
    format!(
        "✏️ *Editar alerta*\n\n*{name}*\n\nEditar ainda não está disponível. Apague e crie de novo.\n\n1. Voltar"
    )
}

pub fn card_caption(listing: &Listing, index: usize, total: usize, headline: Option<&str>) -> String {
    let title = truncate(&plain(&listing.title), 80);
    let condo = json_fee(&listing.properties, "condominio");
    let iptu = json_fee(&listing.properties, "iptu");
    let price = format_listing_price(
        listing.price_value.map(i64::from),
        &listing.listing_kind,
        condo,
        iptu,
    );
    let rooms = json_int(&listing.properties, "rooms")
        .map(|rooms| format!("{rooms} quarto(s)"))
        .unwrap_or_else(|| "—".to_string());
    let area = json_int(&listing.properties, "size")
        .filter(|size| *size > 0)
        .map(|size| format!("{size}m²"))
        .unwrap_or_else(|| "—".to_string());
    let kind = listing
        .properties
        .get("real_estate_type")
        .and_then(|value| value.as_str())
        .unwrap_or("—");
    let neighbourhood = if listing.neighbourhood.is_empty() {
        "—"
    } else {
        listing.neighbourhood.as_str()
    };
    let mut lines = Vec::new();
    if let Some(headline) = headline {
        if !headline.is_empty() {
            lines.push(headline.to_string());
        }
    }
    lines.push(format!("🏠 {title}"));
    lines.push(format!("💰 {price} | 🛏 {rooms} | 📐 {area}"));
    lines.push(format!("📍 {neighbourhood} · {kind}"));
    if !listing.active {
        lines.push("❌ Fora do ar".to_string());
    }
    if listing.url.starts_with("http") {
        lines.push(format!("🔗 {}", listing.url));
    }
    lines.push(String::new());
    lines.push(format!("{} de {total}", index + 1));
    lines.push("1 próximo · 2 anterior · 3 acompanhar · 4 menu".to_string());
    lines.join("\n")
}

pub fn watch_card_caption(listing: &Listing, index: usize, total: usize) -> String {
    let mut caption = card_caption(listing, index, total, None);
    caption = caption.replace(
        "1 próximo · 2 anterior · 3 acompanhar · 4 menu",
        "1 próximo · 2 anterior · 3 parar · 4 menu",
    );
    if listing.active {
        let counter = format!("\n{} de {total}\n", index + 1);
        caption = caption.replacen(&counter, &format!("\n✅ No ar{counter}"), 1);
    }
    caption
}

pub fn pro_pitch(cfg: &Config) -> String {
    format!(
        "\
🚀 *Radar Pro*

Até *{} alertas* e *{} anúncios* acompanhados.

Cadastre seu e-mail e ganhe *{} dias* de Radar Pro grátis.
É só uma vez por conta.

Envie o e-mail, ou *menu* para voltar.",
        cfg.alert_pro_cap, cfg.watch_pro_cap, cfg.email_trial_days
    )
}

pub fn pro_activated(until: DateTime<Utc>, cfg: &Config) -> String {
    format!(
        "✅ *Radar Pro ativado* até {}.\n\nAgora você pode ter até {} alertas e {} anúncios acompanhados.",
        until.format("%d/%m/%Y"),
        cfg.alert_pro_cap,
        cfg.watch_pro_cap
    )
}

pub fn cap_alerts(cfg: &Config, is_pro: bool) -> String {
    if is_pro {
        format!(
            "Você chegou no limite de {} alertas do Radar Pro.",
            cfg.alert_pro_cap
        )
    } else {
        format!(
            "Limite grátis de {} alerta. Digite *pro* e cadastre o e-mail para ganhar {} dias de Radar Pro (até {} alertas).",
            cfg.alert_free_cap, cfg.email_trial_days, cfg.alert_pro_cap
        )
    }
}

pub fn cap_watches(cfg: &Config, is_pro: bool) -> String {
    if is_pro {
        format!(
            "Você chegou no limite de {} anúncios acompanhados.",
            cfg.watch_pro_cap
        )
    } else {
        format!(
            "Limite grátis de {} anúncios. Digite *pro* e cadastre o e-mail para ganhar 1 mês de Radar Pro.",
            cfg.watch_free_cap
        )
    }
}

pub fn watch_price_change(title: &str, old_price: Option<i64>, new_price: Option<i64>, url: &str) -> String {
    let mut body = format!(
        "👀 *Mudança de preço*\n\n*{title}*\n💰 {} → {}",
        format_brl(old_price),
        format_brl(new_price)
    );
    if url.starts_with("http") {
        body.push_str(&format!("\n🔗 {url}"));
    }
    body
}

pub fn watch_removed(title: &str, url: &str) -> String {
    let mut body = format!(
        "👀 *Anúncio fora do ar*\n\n*{title}*\nEsse anúncio saiu do radar (provavelmente removido ou vendido)."
    );
    if url.starts_with("http") {
        body.push_str(&format!("\n🔗 {url}"));
    }
    body
}

pub fn watch_back(title: &str, url: &str) -> String {
    let mut body = format!(
        "👀 *Anúncio de volta*\n\n*{title}*\nEsse anúncio voltou a aparecer no radar."
    );
    if url.starts_with("http") {
        body.push_str(&format!("\n🔗 {url}"));
    }
    body
}

pub fn plain(text: &str) -> String {
    text.replace(['*', '_', '~', '`'], "")
}

fn truncate(text: &str, limit: usize) -> String {
    let count = text.chars().count();
    if count <= limit {
        return text.to_string();
    }
    let mut out: String = text.chars().take(limit.saturating_sub(1)).collect();
    out.push('…');
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recife_rent_presets_match_telegram() {
        let presets = price_presets("aluguel", "Recife");
        assert_eq!(presets[0].max, 2_500);
        assert_eq!(presets[3].min, 7_000);
    }

    #[test]
    fn auto_name_uses_neighbourhood_and_cap() {
        let draft = Draft {
            municipality: Some("Maceió".into()),
            listing_kind: Some("venda".into()),
            categories: vec!["Apartamentos".into()],
            min_price: None,
            max_price: Some(400_000),
            min_rooms: None,
            neighbourhoods: vec!["Ponta Verde".into()],
            alert_name: None,
            pending_raw_neighbourhoods: vec![],
            nl_mode: false,
        };
        assert_eq!(auto_alert_name(&draft), "Apto · Ponta Verde · até R$ 400 mil");
    }

    #[test]
    fn watch_caption_marks_active_listings() {
        let listing = Listing {
            listing_id: 1,
            active: true,
            listing_kind: "venda".into(),
            url: "https://example.com/1".into(),
            title: "Apto".into(),
            price_value: Some(100_000),
            old_price: None,
            municipality: "Maceió".into(),
            neighbourhood: "Ponta Verde".into(),
            category: "Apartamentos".into(),
            images: vec![],
            properties: serde_json::json!({}),
            first_seen_at: None,
        };
        let caption = watch_card_caption(&listing, 0, 1);
        assert!(caption.contains("✅ No ar"));
        assert!(caption.contains("3 parar"));
    }
}
