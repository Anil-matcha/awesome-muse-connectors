---
name: "amadeus"
description: "Search travel with Amadeus: flight offers and prices, airport autocomplete, hotel offers, cheapest dates. Trigger phrases: amadeus, flight search, flight prices, hotel search."
metadata: { "includeInPrompt": true }
tagline: "Search travel with Amadeus: flight offers and prices, airport autocomplete, hotel offers, cheapest dates."
catalog_auth: "OAuth 2.0 client credentials via the secure credential flow"
catalog_hosts: ["test.api.amadeus.com", "api.amadeus.com"]
---

# Amadeus

## Purpose
Search travel with Amadeus Self-Service APIs: flight offers with prices, airport/city autocomplete, hotel offers, cheapest dates. This connector covers search plus pricing: it returns offers and prices, but it does not book tickets. Use when the user wants to search flights or hotels.

## Tooling
All commands go through `bin/amadeus.py`:

```bash
bin/amadeus.py auth                                        # verify the token (test env)
bin/amadeus.py locations --keyword "London"               # airport/city autocomplete
bin/amadeus.py flight-offers --origin JFK --destination LHR --departure-date 2026-10-01 --return-date 2026-10-08
bin/amadeus.py hotel-offers --hotel-ids HTPAR001 --check-in 2026-10-01 --check-out 2026-10-03
bin/amadeus.py flight-dates --origin JFK --destination LHR --departure-date 2026-10-01 --duration 7
```

Pass `--env prod` to any command to use production instead of the test sandbox (default `--env test`).

## Auth
- Provider id: `amadeus` (credential is collected as `custom.amadeus`)
- Collection: OAuth 2.0 client credentials via the secure credential flow (`credentials.request_api_access`); sign up at developers.amadeus.com and create an app to get an API Key + API Secret. The runtime exchanges them at `POST /v1/security/oauth2/token` and hands the CLI a fresh access token as a Bearer credential.
- Allowed hosts: `test.api.amadeus.com`, `api.amadeus.com`
- Status check: `bin/amadeus.py auth` (must return `"ok": true`)

## Operating Rules
1. Cost: the test environment is free but serves limited/cached data; production has real-time data with free-call tiers before billing starts. Stay in `--env test` unless the user explicitly needs live data.
2. Position results honestly: offers and prices are informational. Self-Service booking APIs are a curated subset, and full ticketing needs a commercial agreement, so never promise a booking.
3. Rate limits are roughly 10 requests/second in test and 40 in production; back off on 429s.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/amadeus.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/amadeus.py

## Maturity
🧪 Draft: written from Amadeus's public Self-Service API docs; not yet live-tested end-to-end.
