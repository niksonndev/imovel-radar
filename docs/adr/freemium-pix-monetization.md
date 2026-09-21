# Freemium + Pix monetization

## Status

Accepted

## Context

Imóvel Radar monitors OLX listings in Maceió and notifies users on Telegram.
Acquisition works best with a free entry (Telegram bot, no account form), but
the landing page previously promised unlimited free alerts forever — which
blocks charging later without feeling like a bait-and-switch.

Telegram Stars were considered for in-bot checkout. In Brazil, Pix is the
dominant payment rail; Stars have low consumer familiarity and add Apple/Google
fee friction. We therefore pay with Pix, not Stars.

Product cadence today is daily scrape (~08:00) then notify (~10:00 Maceió).
Marketing that says “continuously / instantly” oversells free and leaves no
room for a paid speed upgrade.

## Decision

Monetize with **freemium + Pix**:

### Free tier (acquisition)

- 1 active alert
- Daily digest (current scraper + notify schedule)
- Full match carousel for that alert
- CTA on the site: “Comece grátis” (not “sem limite”)

### Paid tier — Radar Pro (via Pix)

Target consumer price band: **R$ 14,90 – R$ 19,90 / mês** (exact price set in
frontend content / future billing config).

Included:

- Up to **5** active alerts
- **Faster updates** (multiple scrapes/day when infrastructure supports it;
  until then, Pro is sold as priority matching + multi-alert)
- **Price-drop alerts** (`old_price` → lower `price_value`)
- Filters beyond the free defaults (e.g. particular-only / with photos when
  scrapable)
- Pix checkout (recurring monthly); cancellation in-bot or via support

### Explicitly out of scope (for now)

- Telegram Stars / XTR invoices
- Ads inside alert messages
- Lifetime / one-time unlock deals
- National multi-city coverage as a paid SKU before Maceió Pro converts

### Where this lives

- **Product decision:** this ADR
- **Public copy & prices on the LP:** `apps/frontend/src/content/page-content.ts`
  (and related components). Do not promise “unlimited free” anywhere.
- **Billing implementation** (Pix provider, webhook, entitlement on `users`):
  future work in `apps/bot` — not required to publish honest freemium copy.

## Consequences

**Positive**

- LP and product story stay aligned: free proves value, Pro sells speed and
  volume.
- Pix matches Brazilian payment habits.
- Free tier still feeds GTM → bot open → alert created funnels.

**Trade-offs**

- Pix needs a BR payment provider (and eventual CNPJ/MEI) before charging.
- Until multi-scrape/day ships, Pro messaging must emphasize multi-alert +
  price drops, not false “instant” claims.
- Entitlement checks must be added to alert creation before enforcing limits.

## Alternatives considered

- **Telegram Stars only:** lowest engineering friction for bots, poor fit for
  Brazilian consumers.
- **Free forever / ads:** erodes trust in time-sensitive alerts.
- **Hard paywall from day one:** kills the Telegram viral loop.
