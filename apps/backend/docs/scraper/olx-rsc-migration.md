# OLX: RSC streaming migration

**Date:** 2026-07-19
**Symptom:** `ParseError: Tag <script id="__NEXT_DATA__"> não encontrada ou vazia`

## What changed

OLX moved from Next.js Pages Router to App Router with RSC streaming.
The single `<script id="__NEXT_DATA__">` tag is gone. Page data now
arrives fragmented across multiple chunks:

```html
<script>
  self.__next_f.push([1, '...']);
</script>
```

Concatenating the string element of each chunk (in HTML order) yields
a text blob in RSC Wire Format — not HTML, not a single valid JSON
document. Inside that blob, the ad array still exists as a valid JSON
fragment: `"ads":[...]`. Individual ad shape (subject, priceValue,
listId, location, properties, images, url, date...) is unchanged.

## Gotchas

- More than one `"ads":[` can appear in the payload (e.g. an empty
  related-listings slot). Pick the candidate with the most items
  containing a valid `listId`, don't assume the first match is correct.
- Native-ad placeholder objects can appear inside the real array
  without a `listId`, e.g.
  `{"advertisingId": "advertising-desktop-listing-native-direct", "deviceType": "desktop"}`
  — already filtered by the existing `if ad.get("listId") is None: continue`.

## Fix (`scraper/olx_scraper.py`)

1. `_extract_rsc_payload` — concatenates `__next_f.push` chunks
2. `_find_balanced_json` — bracket-matching (string/escape-aware) to
   isolate the `ads` array
3. `_extract_ads_candidates` — finds and decodes every `"ads":[` match
4. `_extract_next_data` — picks the candidate with the most valid-`listId` items
5. `_extract_ads_payload` — reads `next_data["ads"]` instead of
   `next_data["props"]["pageProps"]["ads"]`

Validated: 2 candidates found, 50 items with valid `listId`, 0 invalid
in final output.

## If OLX changes again

1. Run `python -m scripts.debug_scraper search-all`, check the error
   log — it reports HTML size, page title, candidate count, and
   valid-`listId` count
2. Inspect the auto-saved `debug_last_response.html`
3. Title like "Just a moment" / "Access denied" → anti-bot block, not
   a structure change
4. No `__NEXT_DATA__` and no RSC chunks either → framework likely
   changed again, investigate from scratch
