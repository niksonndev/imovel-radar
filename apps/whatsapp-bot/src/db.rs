use std::time::Duration;

use anyhow::Context;
use chrono::{DateTime, Duration as ChronoDuration, Utc};
use serde_json::Value;
use sqlx::{PgPool, Postgres, QueryBuilder, Row};

use crate::config::Config;
use crate::models::{
    json_strings, Alert, ClaimStatus, CreateAlertStatus, Listing, ListingMatch, User, Watch,
    WatchStatus,
};
use crate::money::{json_fee, effective_listing_price};
use crate::session::{Draft, Session};

const EFFECTIVE_PRICE: &str = "\
CASE
  WHEN listing.listing_kind = 'aluguel' THEN
    listing.price_value
    + COALESCE(GREATEST(CASE WHEN (listing.properties->>'condominio') ~ '^-?[0-9]+$' THEN (listing.properties->>'condominio')::integer ELSE 0 END, 0), 0)
    + COALESCE(GREATEST(CASE WHEN (listing.properties->>'iptu') ~ '^-?[0-9]+$' THEN (listing.properties->>'iptu')::integer ELSE 0 END, 0), 0)
  ELSE listing.price_value
END";

const ROOMS_EXPR: &str = "\
CASE WHEN (listing.properties->>'rooms') ~ '^-?[0-9]+$'
     THEN (listing.properties->>'rooms')::integer ELSE NULL END";

#[derive(Clone)]
pub struct Db {
    pool: PgPool,
}

impl Db {
    pub async fn connect(url: &str) -> anyhow::Result<Self> {
        let pool = sqlx::postgres::PgPoolOptions::new()
            .max_connections(5)
            .acquire_timeout(Duration::from_secs(20))
            .connect(url)
            .await
            .context("conectar no Postgres")?;
        Ok(Self { pool })
    }

    pub async fn ensure_whatsapp_user(&self, jid: &str) -> anyhow::Result<i64> {
        sqlx::query(
            "INSERT INTO users (chat_id, channel, whatsapp_jid)
             VALUES (nextval('whatsapp_user_id_seq'), 'whatsapp', $1)
             ON CONFLICT (whatsapp_jid) DO NOTHING",
        )
        .bind(jid)
        .execute(&self.pool)
        .await?;
        let row = sqlx::query("SELECT chat_id FROM users WHERE whatsapp_jid = $1")
            .bind(jid)
            .fetch_one(&self.pool)
            .await?;
        Ok(row.try_get("chat_id")?)
    }

    pub async fn get_user(&self, chat_id: i64) -> anyhow::Result<Option<User>> {
        let row = sqlx::query(
            "SELECT chat_id, plan, pro_until, email, email_pro_trial_claimed_at, channel, whatsapp_jid
             FROM users WHERE chat_id = $1",
        )
        .bind(chat_id)
        .fetch_optional(&self.pool)
        .await?;
        Ok(row.map(user_from_row).transpose()?.flatten())
    }

    pub fn is_pro(user: Option<&User>, now: DateTime<Utc>) -> bool {
        let Some(user) = user else {
            return false;
        };
        if user.plan != "pro" {
            return false;
        }
        match user.pro_until {
            None => true,
            Some(until) => until > now,
        }
    }

    pub async fn whatsapp_users(&self) -> anyhow::Result<Vec<User>> {
        let rows = sqlx::query(
            "SELECT chat_id, plan, pro_until, email, email_pro_trial_claimed_at, channel, whatsapp_jid
             FROM users WHERE channel = 'whatsapp' ORDER BY chat_id",
        )
        .fetch_all(&self.pool)
        .await?;
        rows.into_iter().map(user_from_row).collect::<Result<Vec<_>, _>>()?
            .into_iter()
            .flatten()
            .collect::<Vec<_>>()
            .pipe_ok()
    }

    pub async fn claim_email(
        &self,
        chat_id: i64,
        email_raw: &str,
        trial_days: i64,
    ) -> anyhow::Result<ClaimStatus> {
        let Some(email) = normalize_email(email_raw) else {
            return Ok(ClaimStatus::InvalidEmail);
        };
        let mut tx = self.pool.begin().await?;
        let user = sqlx::query(
            "SELECT chat_id, plan, pro_until, email, email_pro_trial_claimed_at, channel, whatsapp_jid
             FROM users WHERE chat_id = $1 FOR UPDATE",
        )
        .bind(chat_id)
        .fetch_optional(&mut *tx)
        .await?;
        let Some(user) = user.and_then(|row| user_from_row(row).ok().flatten()) else {
            return Ok(ClaimStatus::InvalidEmail);
        };
        if Self::is_pro(Some(&user), Utc::now()) {
            return Ok(ClaimStatus::AlreadyPro);
        }
        if user.email_pro_trial_claimed_at.is_some() {
            return Ok(ClaimStatus::AlreadyClaimed);
        }
        let taken = sqlx::query(
            "SELECT 1 FROM users WHERE email = $1 AND chat_id <> $2 LIMIT 1",
        )
        .bind(&email)
        .bind(chat_id)
        .fetch_optional(&mut *tx)
        .await?;
        if taken.is_some() {
            return Ok(ClaimStatus::EmailTaken);
        }
        let now = Utc::now();
        let until = now + ChronoDuration::days(trial_days);
        sqlx::query(
            "UPDATE users
             SET plan = 'pro', pro_until = $2, stars_subscription_active = false,
                 email = $3, email_pro_trial_claimed_at = $4
             WHERE chat_id = $1",
        )
        .bind(chat_id)
        .bind(until)
        .bind(&email)
        .bind(now)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(ClaimStatus::Activated { pro_until: until })
    }

    pub async fn neighbourhoods(
        &self,
        municipality: &str,
        listing_kind: Option<&str>,
    ) -> anyhow::Result<Vec<String>> {
        let rows = if let Some(kind) = listing_kind {
            sqlx::query(
                "SELECT neighbourhood FROM listing
                 WHERE municipality = $1 AND neighbourhood <> '' AND listing_kind = $2
                 GROUP BY neighbourhood ORDER BY COUNT(*) DESC",
            )
            .bind(municipality)
            .bind(kind)
            .fetch_all(&self.pool)
            .await?
        } else {
            sqlx::query(
                "SELECT neighbourhood FROM listing
                 WHERE municipality = $1 AND neighbourhood <> ''
                 GROUP BY neighbourhood ORDER BY COUNT(*) DESC",
            )
            .bind(municipality)
            .fetch_all(&self.pool)
            .await?
        };
        Ok(rows
            .into_iter()
            .filter_map(|row| row.try_get::<String, _>("neighbourhood").ok())
            .collect())
    }

    pub async fn alerts_for_user(&self, chat_id: i64) -> anyhow::Result<Vec<Alert>> {
        let rows = sqlx::query(sqlx::AssertSqlSafe(alert_select(
            "WHERE chat_id = $1 ORDER BY id DESC",
        )))
            .bind(chat_id)
            .fetch_all(&self.pool)
            .await?;
        rows.into_iter().map(alert_from_row).collect()
    }

    pub async fn active_alerts(&self, chat_id: i64) -> anyhow::Result<Vec<Alert>> {
        let rows = sqlx::query(sqlx::AssertSqlSafe(alert_select(
            "WHERE chat_id = $1 AND active = true ORDER BY id DESC",
        )))
        .bind(chat_id)
        .fetch_all(&self.pool)
        .await?;
        rows.into_iter().map(alert_from_row).collect()
    }

    pub async fn alert_for_user(&self, chat_id: i64, alert_id: i32) -> anyhow::Result<Option<Alert>> {
        let row = sqlx::query(sqlx::AssertSqlSafe(alert_select(
            "WHERE chat_id = $1 AND id = $2",
        )))
            .bind(chat_id)
            .bind(alert_id)
            .fetch_optional(&self.pool)
            .await?;
        row.map(alert_from_row).transpose()
    }

    pub async fn delete_alert(&self, chat_id: i64, alert_id: i32) -> anyhow::Result<bool> {
        let mut tx = self.pool.begin().await?;
        let exists = sqlx::query("SELECT 1 FROM alerts WHERE id = $1 AND chat_id = $2")
            .bind(alert_id)
            .bind(chat_id)
            .fetch_optional(&mut *tx)
            .await?;
        if exists.is_none() {
            return Ok(false);
        }
        sqlx::query("DELETE FROM alert_matches WHERE alert_id = $1")
            .bind(alert_id)
            .execute(&mut *tx)
            .await?;
        sqlx::query("DELETE FROM alerts WHERE id = $1 AND chat_id = $2")
            .bind(alert_id)
            .bind(chat_id)
            .execute(&mut *tx)
            .await?;
        tx.commit().await?;
        Ok(true)
    }

    pub async fn create_alert(
        &self,
        chat_id: i64,
        draft: &Draft,
        cfg: &Config,
    ) -> anyhow::Result<CreateAlertStatus> {
        let alerts = self.alerts_for_user(chat_id).await?;
        if let Some(existing) = find_equivalent(&alerts, draft) {
            return Ok(CreateAlertStatus::Reused(existing.id));
        }
        let user = self.get_user(chat_id).await?;
        let cap = if Self::is_pro(user.as_ref(), Utc::now()) {
            cfg.alert_pro_cap
        } else {
            cfg.alert_free_cap
        };
        let active = alerts.iter().filter(|alert| alert.active).count() as i64;
        if active >= cap {
            return Ok(CreateAlertStatus::CapReached);
        }
        let neighbourhoods = json_list(&draft.neighbourhoods);
        let categories = json_list(&draft.categories);
        let row = sqlx::query(
            "INSERT INTO alerts (
                chat_id, alert_name, listing_kind, municipality, min_price, max_price,
                min_rooms, neighbourhoods, categories, active
             ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,true)
             RETURNING id",
        )
        .bind(chat_id)
        .bind(draft.alert_name.as_deref())
        .bind(draft.listing_kind.as_deref().unwrap_or("aluguel"))
        .bind(draft.municipality.as_deref().unwrap_or("Maceió"))
        .bind(draft.min_price.map(|value| value as i32))
        .bind(draft.max_price.map(|value| value as i32))
        .bind(draft.min_rooms)
        .bind(neighbourhoods)
        .bind(categories)
        .fetch_one(&self.pool)
        .await?;
        Ok(CreateAlertStatus::Created(row.try_get("id")?))
    }

    pub async fn unnotified(&self, chat_id: i64) -> anyhow::Result<Vec<ListingMatch>> {
        let alerts = self.active_alerts(chat_id).await?;
        let mut matches = Vec::new();
        for alert in alerts {
            let listings = self.unnotified_for_alert(&alert).await?;
            for listing in listings {
                matches.push(ListingMatch {
                    listing,
                    alert_id: alert.id,
                });
            }
        }
        Ok(matches)
    }

    async fn unnotified_for_alert(&self, alert: &Alert) -> anyhow::Result<Vec<Listing>> {
        let sql = format!(
            "SELECT {LISTING_COLUMNS}
             FROM listing
             LEFT JOIN alert_matches am
               ON am.listing_id = listing.listing_id AND am.alert_id = $1
             WHERE listing.active = true
               AND listing.listing_kind = $2
               AND listing.municipality = $3
               AND am.listing_id IS NULL
               AND ($4::int IS NULL OR ({EFFECTIVE_PRICE}) >= $4)
               AND ($5::int IS NULL OR ({EFFECTIVE_PRICE}) <= $5)
               AND ($6::int IS NULL OR ({ROOMS_EXPR}) IS NULL OR ({ROOMS_EXPR}) >= $6)
               AND ($7::text[] IS NULL OR listing.category = ANY($7))
               AND ($8::text[] IS NULL OR listing.neighbourhood = ANY($8))
             ORDER BY listing.updated_at DESC"
        );
        let categories = empty_as_null(&alert.categories);
        let neighbourhoods = empty_as_null(&alert.neighbourhoods);
        let rows = sqlx::query(sqlx::AssertSqlSafe(sql))
            .bind(alert.id)
            .bind(&alert.listing_kind)
            .bind(if alert.municipality.is_empty() {
                "Maceió"
            } else {
                alert.municipality.as_str()
            })
            .bind(alert.min_price)
            .bind(alert.max_price)
            .bind(alert.min_rooms)
            .bind(categories)
            .bind(neighbourhoods)
            .fetch_all(&self.pool)
            .await?;
        rows.into_iter().map(listing_from_row).collect()
    }

    pub async fn mark_notified(&self, pairs: &[(i32, i32)]) -> anyhow::Result<()> {
        if pairs.is_empty() {
            return Ok(());
        }
        let mut builder: QueryBuilder<Postgres> =
            QueryBuilder::new("INSERT INTO alert_matches (alert_id, listing_id) ");
        builder.push_values(pairs, |mut row, (alert_id, listing_id)| {
            row.push_bind(*alert_id).push_bind(*listing_id);
        });
        builder.push(" ON CONFLICT (alert_id, listing_id) DO NOTHING");
        builder.build().execute(&self.pool).await?;
        Ok(())
    }

    pub async fn snapshot(&self) -> anyhow::Result<Option<Value>> {
        let row = sqlx::query(
            "SELECT payload FROM market_snapshot ORDER BY collected_on DESC LIMIT 1",
        )
        .fetch_optional(&self.pool)
        .await?;
        let Some(row) = row else {
            return Ok(None);
        };
        let payload: Value = row.try_get("payload")?;
        Ok(Some(payload))
    }

    pub async fn listing(&self, listing_id: i32) -> anyhow::Result<Option<Listing>> {
        let sql = format!("SELECT {LISTING_COLUMNS} FROM listing WHERE listing_id = $1");
        let row = sqlx::query(sqlx::AssertSqlSafe(sql))
            .bind(listing_id)
            .fetch_optional(&self.pool)
            .await?;
        row.map(listing_from_row).transpose()
    }

    pub async fn create_watch(
        &self,
        chat_id: i64,
        listing_id: i32,
        cfg: &Config,
    ) -> anyhow::Result<WatchStatus> {
        let Some(listing) = self.listing(listing_id).await? else {
            return Ok(WatchStatus::ListingMissing);
        };
        if let Some(existing) = sqlx::query(
            "SELECT id FROM watched_listings WHERE chat_id = $1 AND listing_id = $2",
        )
        .bind(chat_id)
        .bind(listing_id)
        .fetch_optional(&self.pool)
        .await?
        {
            return Ok(WatchStatus::Duplicate(existing.try_get("id")?));
        }
        let count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM watched_listings WHERE chat_id = $1",
        )
        .bind(chat_id)
        .fetch_one(&self.pool)
        .await?;
        let user = self.get_user(chat_id).await?;
        let cap = if Self::is_pro(user.as_ref(), Utc::now()) {
            cfg.watch_pro_cap
        } else {
            cfg.watch_free_cap
        };
        if count >= cap {
            return Ok(WatchStatus::CapReached);
        }
        let baseline = effective_listing_price(
            listing.price_value.map(i64::from),
            &listing.listing_kind,
            json_fee(&listing.properties, "condominio"),
            json_fee(&listing.properties, "iptu"),
        )
        .map(|value| value as i32);
        let row = sqlx::query(
            "INSERT INTO watched_listings (chat_id, listing_id, last_known_price, last_known_active)
             VALUES ($1,$2,$3,$4) RETURNING id",
        )
        .bind(chat_id)
        .bind(listing_id)
        .bind(baseline)
        .bind(listing.active)
        .fetch_one(&self.pool)
        .await?;
        Ok(WatchStatus::Created(row.try_get("id")?))
    }

    pub async fn watches(&self, chat_id: i64) -> anyhow::Result<Vec<Watch>> {
        let sql = format!(
            "SELECT w.id, w.chat_id, w.last_known_price, w.last_known_active,
                    {LISTING_COLUMNS}
             FROM watched_listings w
             JOIN listing ON listing.listing_id = w.listing_id
             WHERE w.chat_id = $1
             ORDER BY w.id DESC"
        );
        let rows = sqlx::query(sqlx::AssertSqlSafe(sql))
            .bind(chat_id)
            .fetch_all(&self.pool)
            .await?;
        rows.into_iter().map(watch_from_row).collect()
    }

    pub async fn delete_watch(&self, chat_id: i64, watch_id: i32) -> anyhow::Result<bool> {
        let result = sqlx::query("DELETE FROM watched_listings WHERE id = $1 AND chat_id = $2")
            .bind(watch_id)
            .bind(chat_id)
            .execute(&self.pool)
            .await?;
        Ok(result.rows_affected() > 0)
    }

    pub async fn changed_watches_whatsapp(&self) -> anyhow::Result<Vec<Watch>> {
        let sql = format!(
            "SELECT w.id, w.chat_id, w.last_known_price, w.last_known_active,
                    {LISTING_COLUMNS}
             FROM watched_listings w
             JOIN listing ON listing.listing_id = w.listing_id
             JOIN users u ON u.chat_id = w.chat_id
             WHERE u.channel = 'whatsapp'
               AND (
                 ({EFFECTIVE_PRICE}) IS DISTINCT FROM w.last_known_price
                 OR listing.active IS DISTINCT FROM w.last_known_active
               )
             ORDER BY w.chat_id, w.id"
        );
        let rows = sqlx::query(sqlx::AssertSqlSafe(sql))
            .fetch_all(&self.pool)
            .await?;
        rows.into_iter().map(watch_from_row).collect()
    }

    pub async fn update_watch_baselines(
        &self,
        updates: &[(i32, Option<i32>, bool)],
    ) -> anyhow::Result<()> {
        for (watch_id, price, active) in updates {
            sqlx::query(
                "UPDATE watched_listings
                 SET last_known_price = $2, last_known_active = $3
                 WHERE id = $1",
            )
            .bind(watch_id)
            .bind(price)
            .bind(active)
            .execute(&self.pool)
            .await?;
        }
        Ok(())
    }

    pub async fn load_session(
        &self,
        chat_id: i64,
        ttl: Duration,
    ) -> anyhow::Result<Option<Session>> {
        let row = sqlx::query(
            "SELECT state, updated_at FROM bot_session WHERE chat_id = $1",
        )
        .bind(chat_id)
        .fetch_optional(&self.pool)
        .await?;
        let Some(row) = row else {
            return Ok(None);
        };
        let updated_at: DateTime<Utc> = row.try_get("updated_at")?;
        if Utc::now() - updated_at > ChronoDuration::from_std(ttl).unwrap_or(ChronoDuration::hours(4))
        {
            self.clear_session(chat_id).await?;
            return Ok(None);
        }
        let state: Value = row.try_get("state")?;
        match serde_json::from_value(state) {
            Ok(session) => Ok(Some(session)),
            Err(error) => {
                tracing::warn!(%error, "sessão inválida; descartando");
                self.clear_session(chat_id).await?;
                Ok(None)
            }
        }
    }

    pub async fn save_session(&self, chat_id: i64, session: &Session) -> anyhow::Result<()> {
        let state = serde_json::to_value(session)?;
        sqlx::query(
            "INSERT INTO bot_session (chat_id, state, updated_at)
             VALUES ($1, $2, now())
             ON CONFLICT (chat_id) DO UPDATE
             SET state = EXCLUDED.state, updated_at = now()",
        )
        .bind(chat_id)
        .bind(state)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    pub async fn clear_session(&self, chat_id: i64) -> anyhow::Result<()> {
        sqlx::query("DELETE FROM bot_session WHERE chat_id = $1")
            .bind(chat_id)
            .execute(&self.pool)
            .await?;
        Ok(())
    }
}

const LISTING_COLUMNS: &str = "\
listing.listing_id, listing.active, listing.listing_kind, listing.url, listing.title,
listing.price_value, listing.old_price, listing.municipality, listing.neighbourhood,
listing.category, listing.images, listing.properties, listing.first_seen_at";

fn alert_select(tail: &str) -> String {
    format!(
        "SELECT id, chat_id, alert_name, listing_kind, municipality, min_price, max_price,
                min_rooms, neighbourhoods, categories, active, created_at
         FROM alerts {tail}"
    )
}

fn user_from_row(row: sqlx::postgres::PgRow) -> anyhow::Result<Option<User>> {
    Ok(Some(User {
        chat_id: row.try_get("chat_id")?,
        plan: row.try_get("plan")?,
        pro_until: row.try_get("pro_until")?,
        email: row.try_get("email")?,
        email_pro_trial_claimed_at: row.try_get("email_pro_trial_claimed_at")?,
        channel: row.try_get("channel")?,
        whatsapp_jid: row.try_get("whatsapp_jid")?,
    }))
}

fn alert_from_row(row: sqlx::postgres::PgRow) -> anyhow::Result<Alert> {
    let neighbourhoods: Option<Value> = row.try_get("neighbourhoods")?;
    let categories: Option<Value> = row.try_get("categories")?;
    Ok(Alert {
        id: row.try_get("id")?,
        chat_id: row.try_get("chat_id")?,
        alert_name: row.try_get("alert_name")?,
        listing_kind: row.try_get("listing_kind")?,
        municipality: row.try_get("municipality")?,
        min_price: row.try_get("min_price")?,
        max_price: row.try_get("max_price")?,
        min_rooms: row.try_get("min_rooms")?,
        neighbourhoods: json_strings(neighbourhoods.as_ref()),
        categories: json_strings(categories.as_ref()),
        active: row.try_get("active")?,
        created_at: row.try_get("created_at")?,
    })
}

fn listing_from_row(row: sqlx::postgres::PgRow) -> anyhow::Result<Listing> {
    let images: Value = row.try_get("images")?;
    let properties: Value = row.try_get("properties")?;
    Ok(Listing {
        listing_id: row.try_get("listing_id")?,
        active: row.try_get("active")?,
        listing_kind: row.try_get("listing_kind")?,
        url: row.try_get("url")?,
        title: row.try_get("title")?,
        price_value: row.try_get("price_value")?,
        old_price: row.try_get("old_price")?,
        municipality: row.try_get("municipality")?,
        neighbourhood: row.try_get("neighbourhood")?,
        category: row.try_get("category")?,
        images: json_strings(Some(&images)),
        properties,
        first_seen_at: row.try_get("first_seen_at")?,
    })
}

fn watch_from_row(row: sqlx::postgres::PgRow) -> anyhow::Result<Watch> {
    Ok(Watch {
        id: row.try_get("id")?,
        chat_id: row.try_get("chat_id")?,
        listing_id: row.try_get("listing_id")?,
        last_known_price: row.try_get("last_known_price")?,
        last_known_active: row.try_get("last_known_active")?,
        listing: listing_from_row(row)?,
    })
}

fn find_equivalent<'a>(alerts: &'a [Alert], draft: &Draft) -> Option<&'a Alert> {
    let mut wanted_nb = draft.neighbourhoods.clone();
    wanted_nb.sort();
    let mut wanted_cats = draft.categories.clone();
    wanted_cats.sort();
    let kind = draft.listing_kind.as_deref().unwrap_or("aluguel");
    let city = draft.municipality.as_deref().unwrap_or("Maceió");
    alerts.iter().find(|alert| {
        let mut nb = alert.neighbourhoods.clone();
        nb.sort();
        let mut cats = alert.categories.clone();
        cats.sort();
        alert.listing_kind == kind
            && (if alert.municipality.is_empty() {
                "Maceió"
            } else {
                alert.municipality.as_str()
            }) == city
            && alert.min_price.map(i64::from) == draft.min_price
            && alert.max_price.map(i64::from) == draft.max_price
            && alert.min_rooms == draft.min_rooms
            && nb == wanted_nb
            && cats == wanted_cats
    })
}

fn empty_as_null(values: &[String]) -> Option<Vec<String>> {
    if values.is_empty() {
        None
    } else {
        Some(values.to_vec())
    }
}

fn json_list(values: &[String]) -> Option<Value> {
    if values.is_empty() {
        None
    } else {
        Some(Value::Array(
            values.iter().cloned().map(Value::String).collect(),
        ))
    }
}

fn normalize_email(raw: &str) -> Option<String> {
    let email = raw.trim().to_lowercase();
    if email.is_empty() {
        return None;
    }
    let Ok(re) = regex::Regex::new(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$") else {
        return None;
    };
    re.is_match(&email).then_some(email)
}

trait PipeOk<T> {
    fn pipe_ok(self) -> anyhow::Result<T>;
}

impl<T> PipeOk<T> for T {
    fn pipe_ok(self) -> anyhow::Result<T> {
        Ok(self)
    }
}
