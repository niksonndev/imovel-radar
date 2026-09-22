# Freemium + Telegram Stars (Pix later)

## Status

Accepted (amended 2026-09-22)

## Context

Imóvel Radar monitors OLX listings in Maceió and notifies users on Telegram.
Acquisition works best with a free entry (Telegram bot, no account form), but
the landing page previously promised unlimited free alerts forever — which
blocks charging later without feeling like a bait-and-switch.

Pix is the preferred long-term rail for Brazilian consumers, but it needs a
merchant account (CNPJ/MEI) and a payment provider. To ship Radar Pro without
that friction, we charge with **Telegram Stars** first and always show a
**BRL equivalent** in copy so the price is understandable.

Product cadence today is daily scrape (~08:00) then notify (~10:00 Maceió).
Marketing that says “continuously / instantly” oversells free and leaves no
room for a paid speed upgrade.

## Decision

Monetize with **freemium + Stars now** (Pix remains the preferred future rail):

### Free tier (acquisition)

- 1 active alert
- Up to **2** watched listings (“Acompanhar anúncio” — price change + deactivation)
- Daily digest (current scraper + notify schedule)
- Full match carousel for that alert
- CTA on the site: “Comece grátis” (not “sem limite”)

### Paid tier — Radar Pro (via Telegram Stars)

- Price: **200 Stars / mês**, marketed as **≈ R$ 19,90 / mês**
- Checkout: in-bot `sendInvoice` with `currency=XTR` and
  `subscription_period=2592000` (30 days)
- Cancel: `/cancelar_pro` → `editUserStarSubscription`, or Telegram Stars settings

Included:

- Up to **5** active alerts
- Up to **10** watched listings
- **Faster updates** (multiple scrapes/day when infrastructure supports it;
  until then, Pro is sold as priority matching + multi-alert)
- **Price-drop alerts** on filter matches (`old_price` → lower `price_value`)
  in addition to per-listing watch notifications (roadmap)
- Filters beyond the free defaults (roadmap)

### Explicitly out of scope (for now)

- Pix provider checkout (deferred until MEI/CNPJ)
- Ads inside alert messages
- Lifetime / one-time unlock deals
- National multi-city coverage as a paid SKU before Maceió Pro converts

### Where this lives

- **Product decision:** this ADR
- **Public copy & prices on the LP:** `apps/frontend/src/content/page-content.ts`
  (and related components). Do not promise “unlimited free” anywhere.
- **Billing implementation:** `apps/bot/handlers/billing.py` + entitlement
  columns on `users` (`plan`, `pro_until`, Stars charge/subscription fields)

## Consequences

**Positive**

- LP and product story stay aligned: free proves value, Pro sells volume.
- No Brazilian merchant KYC required to start charging.
- Entitlement and free caps are enforced in the bot.

**Trade-offs**

- Stars are less familiar in Brazil; BRL equivalent in every sell message
  mitigates that.
- Apple/Google fee friction on Stars purchases.
- Pix remains desirable later for conversion and lower fees.

## Alternatives considered

- **Pix only (Asaas/etc.):** best BR fit, blocked on CNPJ/MEI for now.
- **Free forever / ads:** erodes trust in time-sensitive alerts.
- **Hard paywall from day one:** kills the Telegram viral loop.
