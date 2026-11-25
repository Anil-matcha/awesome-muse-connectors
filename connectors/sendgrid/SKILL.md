---
name: "sendgrid"
description: "Send email with SendGrid: send mail, check stats and profile. Trigger phrases: sendgrid, send an email via sendgrid."
metadata: { "includeInPrompt": true }
tagline: "Send email, check stats and profile."
catalog_auth: "API key (per-user)"
catalog_hosts: ["api.sendgrid.com"]
---

# SendGrid

## Purpose
Send email through SendGrid: send mail, check sending stats, view the account profile. Use when the user mentions SendGrid or wants email sent through it.

## Tooling
All commands go through `bin/sendgrid.py`:

```bash
bin/sendgrid.py auth                                    # verify the API key
bin/sendgrid.py send --from "you@example.com" --to "them@example.com" --subject "Hi" --text "Hello"
bin/sendgrid.py stats                                   # email stats for the last 7 days
bin/sendgrid.py stats --start-date 2026-09-01           # stats from a date
```

## Auth
- Provider id: `sendgrid` (credential is collected as `custom.sendgrid`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in the SendGrid dashboard under Settings > API Keys
- Allowed hosts: `api.sendgrid.com`
- Status check: `bin/sendgrid.py auth` (must return `"ok": true`)

## Operating Rules
1. `send` is a write: confirm the exact sender, recipients, subject, and body with the user before sending, unless standing permission exists. The sender address must be on a verified SendGrid domain.
2. Reading (stats, profile) needs no confirmation.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/sendgrid.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/sendgrid.py

## Maturity
🧪 Draft: written from SendGrid's public API docs; not yet live-tested end-to-end.
