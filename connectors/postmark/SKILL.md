---
name: "postmark"
description: "Send email with Postmark: send transactional mail, check messages and bounces. Trigger phrases: postmark, send via postmark."
metadata: { "includeInPrompt": true }
tagline: "Send transactional email, check delivery and bounces."
catalog_auth: "server API token (per-user)"
catalog_hosts: ["api.postmarkapp.com"]
---

# Postmark

## Purpose
Send email through Postmark: send transactional mail, list recent outbound messages, check bounces. Use when the user mentions Postmark or wants email sent through it.

## Tooling
All commands go through `bin/postmark.py`:

```bash
bin/postmark.py auth                                    # verify the server token
bin/postmark.py send --from "you@example.com" --to "them@example.com" --subject "Hi" --text "Hello"
bin/postmark.py messages --limit 20                     # recent outbound messages
bin/postmark.py bounces --limit 20                      # recent bounces
```

## Auth
- Provider id: `postmark` (credential is collected as `custom.postmark`)
- Collection: server API token via the secure credential flow (`credentials.request_api_access`); created in Postmark under the server's API Tokens tab
- Allowed hosts: `api.postmarkapp.com`
- Status check: `bin/postmark.py auth` (must return `"ok": true`)

## Operating Rules
1. `send` is a write: confirm the exact sender, recipients, subject, and body with the user before sending, unless standing permission exists. The sender must be a verified Postmark domain or sender signature.
2. Keep transactional (`outbound`) and marketing (`broadcast`) streams separate: never mix them; it damages deliverability.
3. Reading (messages, bounces) needs no confirmation.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/postmark.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/postmark.py

## Maturity
🧪 Draft: written from Postmark's public API docs; not yet live-tested end-to-end.
