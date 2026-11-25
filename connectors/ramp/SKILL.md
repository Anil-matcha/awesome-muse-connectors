---
name: "ramp"
description: "Read-only Ramp corporate spend: transactions, cards and card limits, users, departments. No spend actions by design. Trigger phrases: ramp, corporate spend, expense transactions, card spend limits."
metadata: { "includeInPrompt": true }
tagline: "Read-only view of corporate spend: transactions, cards and limits, users, departments. No spend actions by design."
catalog_auth: "OAuth 2.0 client credentials (per-user)"
catalog_hosts: ["api.ramp.com"]
---

# Ramp

## Purpose
Inspect a Ramp corporate-spend account without any ability to move money: list and retrieve transactions, list cards and show their spending restrictions, list users, and list departments. Reach for this when the user wants spend visibility, expense review, or cardholder lookup. It cannot issue cards, set limits, pay bills, or reimburse.

## Tooling
All commands go through `bin/ramp.py`. Read-only, so there is no sandbox/prod split: every call is a GET against `https://api.ramp.com/developer/v1`.

```bash
bin/ramp.py auth                                   # verify the credential
bin/ramp.py transactions --limit 25                # list transactions
bin/ramp.py transactions --limit 50 --from-date 2026-09-01T00:00:00Z --to-date 2026-09-30T23:59:59Z
bin/ramp.py transaction-get --transaction-id TX_ID # one transaction
bin/ramp.py cards --limit 25                       # list cards
bin/ramp.py card-limits --card-id CARD_ID          # spending restrictions on one card
bin/ramp.py users --limit 25                       # list users
bin/ramp.py departments --limit 25                 # list departments
```

## Auth
- Provider id: `ramp` (credential is collected as `custom.ramp`)
- Collection: Ramp API client id and secret (dashboard > Settings > Developer) via the secure credential flow (`credentials.request_api_access`); the runtime exchanges them at `POST /developer/v1/token` (OAuth 2.0 client credentials grant) and hands the CLI a fresh Bearer token
- Auth scheme: `Authorization: Bearer <token>` on every request
- Required scopes: read scopes only, e.g. `transactions:read`, `cards:read`, `users:read`; request no write scopes for this connector
- Allowed hosts: `api.ramp.com`
- Status check: `bin/ramp.py auth`

## Operating Rules
1. This connector stays read-only: it wires only GET endpoints, because one mistyped id or misread instruction in a write-capable connector could issue cards, pay bills, or move funds. Read access needs no confirmation; anything that spends money belongs in a separate, explicit flow.
2. Collect the credential with read-only scopes only. If Ramp adds broader scopes to the stored credential later, this CLI still cannot spend anything because no write code path exists.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/ramp.py`). Do not print, log, or transmit the client secret or tokens.
4. Honesty flags (unverified while building this connector): the single-transaction GET path and the departments list path were not confirmed in the public docs consulted; the CLI surfaces Ramp's own error message if either is absent. `card-limits` reads the card object's `spending_restrictions` field; no separate limits endpoint was verified. Ramp also runs a demo host (`demo-api.ramp.com`), but this CLI targets production only, which is safe because it cannot spend.

## Files
- SKILL.md
- bin/ramp.py

## Maturity
Draft: written from Ramp's public developer docs; not yet live-tested end-to-end.
