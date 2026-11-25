---
name: "wise"
description: "View Wise profiles and multi-currency balances. Read-only by design. Trigger phrases: wise, wise balance, transferwise."
metadata: { "includeInPrompt": true }
tagline: "View Wise profiles and multi-currency balances. Read-only by design."
catalog_auth: "Wise personal API token (per-user, wise.com \u2192 Settings \u2192 API tokens)"
catalog_hosts: ["api.wise.com"]
---

# Wise

## Purpose
Read-only access to the user's Wise account: list profiles and view multi-currency balances per profile. Use when the user mentions Wise or TransferWise, or asks about a Wise balance. Amounts are in major units (e.g. dollars), not cents. This connector cannot move money or change anything.

## Tooling
All commands go through `bin/wise.py`:

```bash
bin/wise.py profiles             # list profiles (also the status check)
bin/wise.py balances --profile P # multi-currency balances for profile P
```

Use `profiles` first to resolve a profile ID for `balances`.

## Auth
- Provider id: `wise` (credential is collected as `custom.wise`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Token: a personal API token from wise.com → Settings → API tokens.
- Allowed hosts: `api.wise.com`
- Status check: `bin/wise.py profiles` (must list profiles without error)
- Connect placement: `bearer_header`

## Operating Rules
1. This connector is read-only by design: `profiles` and `balances` only retrieve data. There are no write commands.
2. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.
3. Report balances exactly as Wise returns them; amounts are in major units, not cents.

## Files
- SKILL.md
- bin/wise.py

## Maturity
🧪 Draft: written from Wise's public API docs; not yet live-tested end-to-end.
