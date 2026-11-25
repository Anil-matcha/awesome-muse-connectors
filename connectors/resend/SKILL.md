---
name: "resend"
description: "Send email through Resend and check delivery status. Trigger phrases: resend, send email, transactional email."
metadata: { "includeInPrompt": true }
tagline: "Send email through Resend and check delivery status. Every send is confirmed with you first."
catalog_auth: "Resend API key (per-user, resend.com/api-keys)"
catalog_hosts: ["api.resend.com"]
---

# Resend

## Purpose
Send email through the Resend API and check delivery status. Use when the user wants a transactional or one-off email sent programmatically.

## Tooling
All commands go through `bin/resend.py`:

```bash
bin/resend.py send --from "you@yourdomain.com" --to "them@example.com" \
    --subject "Hello" --text "body text"     # send an email (returns the email id)
bin/resend.py get --id EMAIL_ID              # check delivery status of a sent email
```

## Auth
- Provider id: `resend` (credential is collected as `custom.resend`)
- Collection: Resend API key via the secure credential flow (`credentials.request_api_access`); create one at resend.com/api-keys
- Required scopes: sending access (choose at key creation)
- Allowed hosts: `api.resend.com`
- Status check: there is no read-only status endpoint; `bin/resend.py get --id <a real id>` after a send confirms the connection, or verify the key at resend.com/api-keys

## Operating Rules
1. **Confirm every send with the user first**: exact `from`, `to`, `subject`, and body. No exceptions, no standing permission.
2. `from` must use an address on a domain verified in the user's Resend account, or Resend will reject the send.
3. `to` accepts a single address (comma-separate for more, but confirm each).
4. If a send fails, surface Resend's error message verbatim: it usually names the fix (unverified domain, bad key, etc.).
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/resend.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/resend.py

## Maturity
🧪 Draft: written from Resend's public API docs; not yet live-tested end-to-end.
