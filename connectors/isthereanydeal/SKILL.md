---
name: "isthereanydeal"
description: "PC game prices, current deals, historical lows, and price history across game stores (Steam, GOG, Epic, Humble, and 30+ more) through the IsThereAnyDeal API v2. Trigger phrases: isthereanydeal, itad, game deals, steam deals, game price check, historical low, price history, where is a game cheapest."
metadata: { "includeInPrompt": true }
tagline: "Check game prices and deals across 30+ PC game stores, with historical lows and price history, through the IsThereAnyDeal API."
catalog_auth: "API key from a free IsThereAnyDeal account (email verified, app registered at isthereanydeal.com/apps), held in a Muse credential connection and sent as the ITAD-API-Key header (placement custom_header). Use the API key, not the OAuth client ID or secret; the core deal endpoints accept only the API key."
catalog_hosts: ["api.isthereanydeal.com"]
---

# IsThereAnyDeal

## Purpose

[IsThereAnyDeal](https://isthereanydeal.com) aggregates prices for PC games across more than 30 stores (Steam, GOG, Epic Game Store, Humble Store, and others) and tracks each game's price history and historical lows. This connector wraps its REST API v2 (OpenAPI spec at [docs.isthereanydeal.com](https://docs.isthereanydeal.com/)) in a small read-only CLI, so Muse can answer "is this game on sale anywhere", "what is the cheapest it has ever been", and "show me the best current deals" with real data instead of web scraping.

The API's coverage used here: game search and lookup, current prices and price overview, recorded price history, the cross-store deals list, bundles, giveaways, all-time and per-store historical lows, subscription-service availability, store lists, and popularity stats. Steam is shop ID 61, GOG is 35, Epic Game Store is 16, Humble Store is 37.

## Auth

A single API key, obtained by creating a free IsThereAnyDeal account, verifying the email address, registering an app at [isthereanydeal.com/apps](https://isthereanydeal.com/apps), and copying the API key from the app page. Register the key as a Muse credential connection:

```json
{
  "provider": "isthereanydeal",
  "auth_scheme": "api_key",
  "placement": "custom_header:ITAD-API-Key",
  "api_hosts": ["api.isthereanydeal.com"]
}
```

The helper attaches the credential through Muse's credential surrogate, so the real key is swapped in only on an approved request to the registered host. Never put the key in a file, command argument, environment variable, or log, and never ask the user to paste it in chat. Keep redirects disabled on authenticated requests.

The rate limit is 1,000 requests per 5 minutes for an account with a verified email. A 429 means the limit was hit; wait for the `Retry-After` window.

Three endpoints under `/lookup/` (game ID by exact title, game ID by shop ID, and the reverse) and the `/service/shops/` lists accept requests with no key at all; everything else needs the key. OAuth exists but covers only user data (collection, waitlist, notes, profiles) and is not used: search, prices, info, and history accept only the API key.

## Tooling

`itad.py` — a helper CLI in pure Python standard library. It prints JSON to stdout and a compact error JSON to stderr. Commands (23):

| Command | What it does |
|---|---|
| `search "<title>" [--results N]` | Search games by title; returns ITAD game IDs |
| `lookup --title "<title>"` / `lookup --appid <steam-appid>` | Look up one game by exact title or Steam app ID |
| `info <game-id>` | Basic info: Steam appid, tags, release date, developers, publishers, review scores |
| `prices <id1,id2> [--country US] [--shops 61] [--deals-only]` | Current prices across stores, with all-time, 1-year, and 3-month historical lows |
| `overview <id1,id2> [--country US]` | Current best price, historical low, and active bundles per game |
| `history <game-id> [--country US]` | Recorded price history for one game in one country |
| `deals [--limit N] [--offset N] [--sort -cut] [--shops 61]` | Current deals list, one entry per game at its best sale price |
| `check "<title>"` | Search plus price check of the top match in one call |
| `bundles` / `game-bundles <game-id>` | Active bundles, overall or for one game |
| `giveaways` / `game-giveaways <game-id>` | Active giveaways, overall or for one game |
| `historylow <id1,id2>` | All-time historical low per game |
| `storelow <id1,id2> [--shops 61]` | Per-store historical lows |
| `subs <id1,id2>` | Subscription services a game is available on |
| `stats most-collected\|most-popular\|most-waitlisted` | Popularity rankings |
| `waitlist-stats` | Most-waitlisted games by country/shop |
| `shops` / `shops-map` | Every tracked shop with its ID (public, no key needed) |
| `gid-title "<title1,title2>"` | ITAD game IDs by exact title (POST `/lookup/id/title/v1`, no key needed) |
| `gid-shop "app/<appid>" --shop 61` | ITAD game ID by shop game ID (no key needed) |
| `shop-ids <game-id> --shop 61` | Shop game ID for an ITAD game ID (no key needed) |

`gid-title` is an exact title match, not a search; a typo can return null. Keep the game `id` from search or lookup, it is the input for prices, info, and history.

Deliberately not covered: the OAuth-only paths (collection, waitlist, ignored list, notifications, profiles, user notes, webhooks), the `/internal/` paths (IsThereAnyDeal's own services), and the `/unstable/` paths.

## Setup

1. Create a free IsThereAnyDeal account and verify the email address.
2. Register an app at [isthereanydeal.com/apps](https://isthereanydeal.com/apps) and copy the API key (not the OAuth client ID or secret).
3. Register the credential connection with the JSON in the Auth section, and complete the secure capture so the key lands in Muse's credential store.
4. Run a first check: `itad.py search "<any game title>" --results 3`, then `itad.py check "<same title>"` for a price result.

## Files

- `bin/itad.py` — the helper CLI (pure Python standard library, no dependencies).
- `connector.yaml` — connector descriptor (title, description, aliases `ITAD`, `isthereanydeal.com`).
- `CONNECTOR.md` — full operating doc: endpoints, parameters, error handling, and limits.

## Operating rules

- **Read-only.** This connector never buys, wishlists, or changes anything; it only reads prices and metadata.
- **Credit IsThereAnyDeal when presenting its data**, and never change its prices or strip the affiliate tags from its deal URLs. Private personal use is allowed under the IsThereAnyDeal API terms.
- **Cloudflare egress note:** the API sits behind Cloudflare bot policies, and some datacenter egress IPs are hard-blocked at the edge: the request returns 403 with the plain body `Your request was blocked.`, before any credential is read, and even for the public no-key endpoints. It is not an auth failure, and changing the User-Agent, forcing IPv4, or switching to OAuth does not help. The remedies are an allowlist from the site owner (Cloudflare's own documented fix, identified by the request's Ray ID) or running the calls from an unblocked egress, for example a small relay host that adds the `ITAD-API-Key` header server-side from a locked-down key file and forwards only the API paths.
- A 401 or 403 that actually reaches IsThereAnyDeal (a JSON error body, not the Cloudflare text above) means the key was rejected: check the header placement first, and reconnect the credential only if a request that carried it is still rejected.

## Maturity

Working and verified live (2026-11-28): authenticated search and price checks return real current data (game IDs, cross-store prices, cuts, and historical lows), and the public shops list and ID lookups return the full tracked-store list. The remaining keyed commands (bundles, giveaways, lows, subs, stats) are built directly from the published OpenAPI spec and run through the same lane, but have not each been individually exercised yet.
