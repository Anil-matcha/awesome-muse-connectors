---
name: "market-evidence-check"
description: "Read-only OKX public order-book cost and freshness check. Trigger phrases: OKX cost check, order book impact, quote freshness, market evidence check."
metadata: { "includeInPrompt": true }
tagline: "Read-only OKX cost/freshness evidence for a stated size. No key, no trading."
catalog_auth: "None (public OKX order-book data; no API key, account, or wallet)"
catalog_hosts: ["devday.167-179-82-72.nip.io"]
---

# Market Evidence Check

## Purpose
Read-only pre-execution evidence for a stated OKX instrument, side, and hypothetical USDT notional. It reads a public OKX order-book snapshot and returns spread, estimated price impact, estimated one-way cost against a declared bps budget, quote age, and displayed-depth checks. Use when the user wants to check market cost/freshness before deciding anything themselves.

GO only means the declared checks passed on that public snapshot. It is not a buy/sell recommendation, trading signal, profit prediction, fill guarantee, or permission to trade.

## Tooling
All commands go through `bin/market_evidence_check.py` (Python standard library only):

```bash
bin/market_evidence_check.py health
bin/market_evidence_check.py check --instrument BTC-USDT --side buy --notional-usdt 1000 --max-cost-bps 30
```

The check prints one JSON object: the API response plus `http_status`. Valid inputs return a report with `decision`, `reason_codes`, `market_evidence`, `execution_cost`, `policy_checks`, `policy_version`, and `evidence_hash`.

## Auth
- Provider id: `market-evidence-check`
- Collection: none. Never ask for an API key, exchange credential, account login, wallet, password, seed phrase, or private key. If any step appears to require credentials, stop and report that as a blocker.
- Required scopes: none
- Allowed hosts: `devday.167-179-82-72.nip.io`
- Status check: `bin/market_evidence_check.py health` (expect HTTP 200 and `status: "ok"`)
- Public API source: OpenAPI at https://raw.githubusercontent.com/yijigao/market-evidence-check-devday/main/connectors/muse/openapi.json (checked 2026-10-06)

## Operating Rules
1. Read-only only: this connector reads public OKX order-book data. It never places, modifies, or cancels an order; never accesses an account or wallet; never signs anything.
2. Fail closed: if the API returns WATCH, REJECT, HTTP 400, HTTP 502, invalid JSON, or a timeout, report it as shown. Never convert a failure into GO and never suggest placing an order.
3. HTTP 200 alone is not GO; always inspect `decision` and `report_status`.
4. Separate observed snapshot values from caller-supplied cost assumptions (`taker_fee_bps`, `slippage_buffer_bps`; policy defaults 10 bps and 2 bps). Label assumptions as assumptions, never as the user's actual account fees.
5. Do not change the user's stated `max_cost_bps` limit without telling them first.
6. This is market evidence, not financial advice.

## Files
- SKILL.md
- bin/market_evidence_check.py

## Maturity
🧪 Draft: CLI live-tested against the public API on 2026-10-06 (health HTTP 200; BTC-USDT sample GO; invalid side HTTP 400 / REJECT). Catalog one-paste install path not yet externally installed.
