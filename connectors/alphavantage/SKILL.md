---
name: "alphavantage"
description: "Stock quotes and daily price history. Trigger phrases: stock quote, alphavantage, stock price."
metadata: { "includeInPrompt": true }
tagline: "Stock quotes and daily price history. Read-only."
catalog_auth: "Alpha Vantage API key (per-user, alphavantage.co/support/#api-key; free tier 25 calls/day)"
catalog_hosts: ["www.alphavantage.co"]
---

# Alpha Vantage

## Purpose
Read-only stock market data: latest quote for a symbol and the last 5 daily closes. Use when the user asks for a stock quote, a stock price, or mentions Alpha Vantage.

## Tooling
All commands go through `bin/alphavantage.py`:

```bash
bin/alphavantage.py quote --symbol IBM    # latest quote
bin/alphavantage.py daily --symbol AAPL   # last 5 daily closes
```

## Auth
- Provider id: `alphavantage` (credential is collected as `custom.alphavantage`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Get a key: alphavantage.co/support/#api-key (free tier: 25 calls/day, 5/minute)
- Allowed hosts: `www.alphavantage.co`
- Status check: `bin/alphavantage.py quote --symbol IBM`
- Connect placement: `query_param:apikey`

## Operating Rules
1. This connector is read-only: it only reads market data. It never trades, never modifies anything, and never sends anything on the user's behalf.
2. Respect the free tier limits (25 calls/day, 5/minute): batch symbols into as few calls as possible and never retry aggressively; if the API returns a rate-limit "Note", back off and tell the user.
3. Alpha Vantage returns HTTP 200 even for errors; the CLI inspects the JSON body for "Error Message", "Note", and "Information" and exits with a clean error: report that error verbatim instead of inventing a quote.
4. This is market data, not financial advice.
5. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/alphavantage.py

## Maturity
🧪 Draft: written from Alpha Vantage's public API docs; not yet live-tested end-to-end.
