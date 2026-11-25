---
name: "fxmacrodata"
description: "Macroeconomic releases, release calendars, and FX spot rates from official sources. Read-only. Trigger phrases: fxmacrodata, cpi release, inflation data, non-farm payrolls, policy rate, economic calendar, fx rate."
metadata: { "includeInPrompt": true }
tagline: "Macro indicator history, release calendars, and FX spot rates for 22 currencies. Read-only; USD works without a key."
catalog_auth: "FXMacroData API key (per-user, optional for USD data)"
catalog_hosts: ["api.fxmacrodata.com"]
---

# FXMacroData

## Purpose
Read-only macroeconomic and FX data from [FXMacroData](https://fxmacrodata.com/?utm_source=github&utm_medium=referral&utm_campaign=awesome-muse-connectors&utm_content=readme): the indicator catalogue for a currency, the release history of one indicator (CPI, payrolls, policy rate, bond yields and so on, each row with its official source link), upcoming release dates, and daily FX spot rates. Use when the user asks for a macro release, an economic calendar, or an exchange rate.

Currencies: AUD, BRL, CAD, CHF, CNH, CNY, DKK, EUR, GBP, HUF, ILS, JPY, KRW, MYR, NGN, NOK, NZD, PEN, SEK, THB, TWD, USD.

Source: the public OpenAPI spec at https://api.fxmacrodata.com/openapi.json and the reference at https://fxmacrodata.com/documentation/reference, both checked on 2026-10-04.

## Tooling
All commands go through `bin/fxmacrodata.py`. Each prints the API's JSON response unchanged.

```bash
bin/fxmacrodata.py status                                   # GET /v1/health, plus which auth mode is in use
bin/fxmacrodata.py catalogue USD                            # GET /v1/data_catalogue/USD: indicator slugs, units, coverage
bin/fxmacrodata.py history USD inflation --limit 12         # GET /v1/announcements/USD/inflation, most recent first
bin/fxmacrodata.py history USD non_farm_payrolls --start 2026-01-01 --end 2026-09-30
bin/fxmacrodata.py calendar USD --start 2026-10-01 --end 2026-10-31   # GET /v1/calendar/USD
bin/fxmacrodata.py calendar USD --indicator inflation
bin/fxmacrodata.py forex EUR USD --limit 20                 # GET /v1/forex/EUR/USD (API key required)
```

`history` and `forex` take `--start`/`--end` (YYYY-MM-DD) and `--limit` (1-100). `calendar` takes `--indicator`, `--start`, and `--end`. Use `catalogue` to find the indicator slug before calling `history`.

## Auth
- Provider id: `fxmacrodata` (credential is collected as `custom.fxmacrodata`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`). Outside Muse, the CLI reads the key from the `FXMACRODATA_API_KEY` environment variable. It never accepts a key as an argument.
- Connect placement: `custom_header:X-API-Key` (the key is never put in the query string)
- Required scopes: none; the API has no scopes. Access depends on the key's plan.
- Allowed hosts: `api.fxmacrodata.com` (HTTPS only; redirects to any other host are refused)
- Status check: `bin/fxmacrodata.py status`. The health check does not need a key; `bin/fxmacrodata.py forex EUR USD --limit 1` confirms a key works.

Without a key, USD data still works: catalogue, history, and calendar. The catalogue answers for every currency. Keyless USD history is delayed by 15 minutes and limited to the last 90 days. Those responses carry `freemium_delay` and `freemium_window` objects, which the CLI also summarises on stderr. Other currencies' history and calendar, and all FX rates, return HTTP 401 `api_key_required` without a key.

## Operating Rules
1. This connector is read-only: every call is a GET. It never places trades, changes an account, or sends anything on the user's behalf.
2. When `freemium_delay.withheld_count` is above zero, a newer release exists but is not shown yet. Say so and do not present the older value as the latest.
3. When `freemium_window` is present, the history was cut to the last 90 days. Do not describe it as the full series.
4. Report HTTP errors verbatim (`api_key_required`, `invalid_api_key`, and so on). A 401 means the data needs a key, not that it is missing.
5. Quote the row's `source` and `source_url` when citing a figure. This is data, not financial advice.
6. Never print, log, or transmit the key value.

## Files
- SKILL.md
- bin/fxmacrodata.py

## Maturity
🧪 Draft: keyless USD commands (`status`, `catalogue`, `history`, `calendar`) were live-tested against api.fxmacrodata.com on 2026-10-04, as was the 401 path for `forex` and non-USD history. Keyed calls and the Muse credential flow have not been tested end-to-end.
