---
name: "gumroad"
description: "View your Gumroad products and sales. Read-only by design. Trigger phrases: gumroad, gumroad sales, gumroad products."
metadata: { "includeInPrompt": true }
tagline: "View your Gumroad products and sales. Read-only by design."
catalog_auth: "Gumroad access token (per-user, app.gumroad.com \u2192 Settings \u2192 Advanced)"
catalog_hosts: ["api.gumroad.com"]
---

# Gumroad

## Purpose
Read-only access to the user's Gumroad account: list products and view recent sales. Use when the user mentions Gumroad, asks about Gumroad sales, or wants to see their Gumroad products. Prices are reported in USD (the API returns cents; the CLI converts). This connector cannot change anything.

## Tooling
All commands go through `bin/gumroad.py`:

```bash
bin/gumroad.py auth             # verify the connection
bin/gumroad.py products         # list products
bin/gumroad.py sales --limit 20 # recent sales
```

## Auth
- Provider id: `gumroad` (credential is collected as `custom.gumroad`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Token: generated at app.gumroad.com/settings/advanced#application-form. Personal tokens have full account access; this skill is read-only regardless.
- Allowed hosts: `api.gumroad.com`
- Status check: `bin/gumroad.py auth` (must return `"ok": true`)
- Connect placement: `bearer_header`

## Operating Rules
1. This connector is read-only by design: `auth`, `products`, and `sales` only retrieve data. There are no write commands.
2. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.
3. Buyer emails from `sales` may be hashed or redacted by Gumroad for privacy; do not treat them as complete contact details.

## Files
- SKILL.md
- bin/gumroad.py

## Maturity
🧪 Draft: written from Gumroad's public API docs; not yet live-tested end-to-end.
