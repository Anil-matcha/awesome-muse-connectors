---
name: "equibles"
description: "US stock research data: SEC filing and earnings call search with line-level reads, XBRL financial statements, earnings calls, Form 4 insider trades, 13F holders, congressional trades and daily prices. Read-only. Trigger phrases: equibles, sec filing, 10-k, earnings call, insider trades, 13f holders, congress trades, income statement."
metadata: { "includeInPrompt": true }
tagline: "SEC filings and transcripts with line-level citations, XBRL statements, insider, 13F and congressional trades, daily prices. Read-only; free plan 100 requests a day."
catalog_auth: "Equibles API key (per-user, free plan available)"
catalog_hosts: ["api.equibles.com"]
---

# Equibles

## Purpose
Read-only US stock market data from [Equibles](https://equibles.com): search SEC filings and earnings call transcripts and read the exact numbered lines behind an answer, pull income, balance sheet and cash-flow statements from SEC XBRL, look up a quarter's earnings call, Form 4 insider transactions, 13F institutional holders, congressional trades and daily end-of-day prices. Use it when the user asks what a company said in a filing or on a call, how its financials moved, or who has been buying or selling the stock.

Source: the public OpenAPI spec at https://api.equibles.com/openapi/v1.json and the REST reference at https://equibles.com/docs/api, both checked on 2026-10-19. Equibles also runs a hosted MCP server for MCP clients (https://equibles.com/mcp); this skill uses the REST API.

## Tooling
All commands go through `bin/equibles.py`. Each prints the API's JSON response unchanged.

```bash
bin/equibles.py status                                              # GET /v1/market/status, plus which auth mode is in use
bin/equibles.py search "artificial intelligence risk" --ticker JPM --type 10-K --limit 2   # GET /v1/stocks/JPM/filings/search
bin/equibles.py search "tariff impact on gross margin" --limit 5    # GET /v1/filings/search across all companies
bin/equibles.py lines 5bdbf4fd-c262-45e0-a91f-6576a3957ce1 238 240  # GET /v1/filings/{documentId}/lines
bin/equibles.py statement AAPL income --year 2025 --period FY       # GET /v1/stocks/AAPL/financial-statements/income
bin/equibles.py call NVDA 2026 2                                    # GET /v1/stocks/NVDA/earnings-calls/2026/2
bin/equibles.py insiders NVDA --type Buy --limit 10                 # GET /v1/stocks/NVDA/insider-transactions
bin/equibles.py holders NVDA --limit 10                             # GET /v1/stocks/NVDA/institutional-holders
bin/equibles.py congress --ticker NVDA --type Purchase --limit 10   # GET /v1/congress/trades
bin/equibles.py prices AAPL --start 2026-09-01 --end 2026-09-30     # GET /v1/stocks/AAPL/prices
```

`search` returns excerpts with a `documentId` and `startLineNumber`; pass them to `lines` to quote the surrounding text (at most 500 lines per call). `statement` takes `income`, `balance` or `cashflow`; omit `--year` and `--period` for the latest period. `--limit` is 1-100 everywhere.

## Auth
- Provider id: `equibles` (credential is collected as `custom.equibles`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`). Users create a key at https://equibles.com/dashboard/apikeys. Outside Muse, the CLI reads the key from the `EQUIBLES_API_KEY` environment variable. It never accepts a key as an argument.
- Connect placement: `bearer_header` (`Authorization: Bearer <key>`; the key is never put in the query string)
- Required scopes: none; the API has no scopes. Access depends on the key's plan: the free plan allows 100 requests a day across MCP and REST, and paid plans start at $9.99 a month (https://equibles.com/pricing).
- Allowed hosts: `api.equibles.com` (HTTPS only; redirects to any other host are refused)
- Status check: `bin/equibles.py status`. Every endpoint needs a key; a missing or deleted key returns HTTP 401 `unauthorized`.

## Operating Rules
1. This connector is read-only: every call is a GET. It never places trades, edits a portfolio or watchlist, or sends anything on the user's behalf.
2. Each command is one API request and counts toward the key's daily allowance. Prefer one targeted `search` plus `lines` over many broad searches.
3. When quoting a filing or transcript, cite the company, form, filed date and line numbers from the response, and read the lines with `lines` before quoting.
4. Insider rows carry `transactionCode` and `isOpenMarketTrade`; gifts, awards, tax withholding and exercises are not open-market buys or sells, so check those fields before describing a trade.
5. Congressional trade amounts are the disclosed STOCK Act value bands, not exact figures; `filingDate` is when the trade became public.
6. Report HTTP errors verbatim (401 `unauthorized`, 429 when the daily allowance is used up). A 401 means the key is missing or invalid, not that the data is missing.
7. Present results as data, not investment advice. Never print, log, or transmit the key value.

## Files
- SKILL.md
- bin/equibles.py

## Maturity
🧪 Draft: every command (`status`, `search` with and without `--ticker`, `lines`, `statement`, `call`, `insiders`, `holders`, `congress`, `prices`) was live-tested against api.equibles.com on 2026-10-19 with a temporary key on a paid plan, as was the 401 path for an invalid key. The free-plan allowance and the Muse credential flow have not been tested end-to-end.
