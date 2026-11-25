---
name: "paddle"
description: "View Paddle transactions and customers. Read-only by design. Trigger phrases: paddle, paddle transactions, paddle customers."
metadata: { "includeInPrompt": true }
tagline: "View Paddle transactions and customers. Read-only by design."
catalog_auth: "Paddle API key (per-user, Paddle Dashboard \u2192 Developer Tools \u2192 Authentication)"
catalog_hosts: ["api.paddle.com"]
---

# Paddle

## Purpose
Read-only access to the user's Paddle account: view transactions and customers. Use when the user mentions Paddle or asks about Paddle transactions or customers. This connector cannot create charges, refunds, or change anything.

## Tooling
All commands go through `bin/paddle.py`:

```bash
bin/paddle.py auth                    # verify the connection (via event-types)
bin/paddle.py transactions --limit 10 # recent transactions
bin/paddle.py customers --limit 10    # customers
```

## Auth
- Provider id: `paddle` (credential is collected as `custom.paddle`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Token: an API key from the Paddle Dashboard → Developer Tools → Authentication (live keys start with `pdl_live_`). Sandbox keys only work against `sandbox-api.paddle.com`; this skill targets production (`api.paddle.com`).
- Allowed hosts: `api.paddle.com`
- Status check: `bin/paddle.py auth` (must return `"ok": true`)
- Connect placement: `bearer_header`

## Operating Rules
1. This connector is read-only by design: `auth`, `transactions`, and `customers` only retrieve data. There are no write commands.
2. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.
3. `transactions` and `customers` cap `per_page` at 200 (the API maximum); the default page size is 10.

## Files
- SKILL.md
- bin/paddle.py

## Maturity
🧪 Draft: written from Paddle's public API docs; not yet live-tested end-to-end.
