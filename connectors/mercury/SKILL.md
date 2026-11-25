---
name: "mercury"
description: "View Mercury bank accounts and transactions. Read-only by design. Trigger phrases: mercury, mercury balance, mercury transactions."
metadata: { "includeInPrompt": true }
tagline: "View Mercury bank accounts and transactions. Read-only by design."
catalog_auth: "Mercury API token (per-user, app.mercury.com \u2192 Settings \u2192 API Tokens; a Read-Only token suffices)"
catalog_hosts: ["api.mercury.com"]
---

# Mercury

## Purpose
Read-only access to the user's Mercury banking: list bank accounts and view recent transactions per account. Use when the user mentions Mercury, asks about a Mercury balance, or wants Mercury transactions. This connector cannot move money or change anything.

## Tooling
All commands go through `bin/mercury.py`:

```bash
bin/mercury.py auth                                # verify the connection
bin/mercury.py accounts                            # list bank accounts
bin/mercury.py transactions --account A --limit 20 # recent transactions for account A
```

Use `accounts` first to resolve an account ID for `transactions`.

## Auth
- Provider id: `mercury` (credential is collected as `custom.mercury`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Token: generated at app.mercury.com → Settings → API Tokens. Use a Read-Only token (no IP whitelist needed); Read+Write tokens require IP whitelisting.
- Allowed hosts: `api.mercury.com`
- Status check: `bin/mercury.py auth` (must return `"ok": true`)
- Connect placement: `bearer_header`

## Operating Rules
1. This connector is read-only by design: `accounts` and `transactions` only retrieve data. There are no write commands.
2. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.
3. Resolve the account ID with `accounts` before calling `transactions`; do not guess account IDs.

## Files
- SKILL.md
- bin/mercury.py

## Maturity
🧪 Draft: written from Mercury's public API docs; not yet live-tested end-to-end.
