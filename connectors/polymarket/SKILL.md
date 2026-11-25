---
name: "polymarket"
description: "Read-only Polymarket market data: events, markets, prices, order books. No trading, no key needed. Trigger phrases: polymarket, prediction markets, market odds, event prices."
metadata: { "includeInPrompt": true }
tagline: "Read-only prediction market data: events, markets, prices, order books. No trading, no API key needed."
catalog_auth: "none, public API"
catalog_hosts: ["gamma-api.polymarket.com"]
---

# Polymarket

## Purpose
Read public Polymarket market data with no key and no account: search and list markets, fetch one market, pull price history, snapshot a public order book, and list or fetch events. Reach for this when the user wants prediction-market odds, event discovery, or price context. This connector cannot trade, place orders, or touch positions.

## Tooling
All commands go through `bin/polymarket.py`. No auth, no environment flags:

```bash
bin/polymarket.py markets --limit 25                    # list markets
bin/polymarket.py markets --search "bitcoin"            # search markets
bin/polymarket.py markets --active --order volume24hr   # active, sorted by 24h volume
bin/polymarket.py market-get --condition-id COND_ID     # one market by condition id
bin/polymarket.py market-get --slug fed-decision-in-october  # one market by slug
bin/polymarket.py prices --condition-id COND_ID --interval 1d  # price history
bin/polymarket.py orderbook --token-id TOKEN_ID         # public order-book snapshot
bin/polymarket.py events --limit 25                     # list events
bin/polymarket.py events --slug fed-decision-in-october # one event by slug
```

Market objects carry `outcomes`, `outcomePrices`, and `clobTokenIds` (the Yes/No token ids, needed for `orderbook`), plus `bestBid`, `bestAsk`, `lastTradePrice`, `spread`, and `oneDayPriceChange` for quick pricing without extra calls.

## Auth
- Provider id: none. The Gamma API is public and requires no key.
- This connector never touches the credential helper and never handles a secret. There is nothing to collect and nothing to store.
- Allowed hosts: `gamma-api.polymarket.com`, `clob.polymarket.com`
- Status check: `bin/polymarket.py events --limit 1` (a successful response proves reachability)

## Operating Rules
1. **Trading is intentionally out of scope.** No order placement, no positions, no signed calls ship in this connector. Market data informs; money movement needs a separate, explicit build.
2. Order books are public snapshots. The CLI pulls them from the CLOB REST endpoint (`clob.polymarket.com/book`), top 10 levels each side. Not a live stream.
3. The Gamma API is public but still rate-limited; keep request volume modest and reuse results instead of re-polling.
4. Two things stayed unverified. The `/markets/slug/{slug}` path never appeared in the docs I read, so use `--condition-id` if it errors. The price-history `interval` values (`1h`, `6h`, `1d`, `1w`, `max`) come from community docs, not the official reference; the API errors on values it does not support.

## Files
- SKILL.md
- bin/polymarket.py

## Maturity
Draft: written from Polymarket's public Gamma docs; not yet live-tested end-to-end.
