---
name: "buttondown"
description: "Read and write Buttondown: list subscribers and emails, add subscribers, draft emails. Trigger phrases: buttondown, newsletter subscribers, email list."
metadata: { "includeInPrompt": true }
tagline: "Read and write Buttondown: list subscribers and emails, add subscribers, draft emails."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.buttondown.com"]
---

# Buttondown

## Purpose
Read and write the user's Buttondown newsletter: list subscribers, list emails (drafts and sent), add subscribers, create email drafts. Use when the user mentions Buttondown or their newsletter.

## Tooling
All commands go through `bin/buttondown.py`:

```bash
bin/buttondown.py auth                                      # verify the API key
bin/buttondown.py subscribers --limit 25                    # list subscribers
bin/buttondown.py subscriber-add --email "them@example.com" # add a subscriber
bin/buttondown.py emails --limit 25                         # list emails
bin/buttondown.py email-create --subject "Hi" --body "..."   # create a draft email
bin/buttondown.py email-create --subject "Hi" --body "..." --send  # send to the list (confirm first)
```

Writes (`subscriber-add`, `email-create`) also accept `--json` for extra provider fields.

## Auth
- Provider id: `buttondown` (credential is collected as `custom.buttondown`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in Buttondown under Settings > API
- Allowed hosts: `api.buttondown.com`
- Status check: `bin/buttondown.py auth` (must return `"ok": true`)

## Operating Rules
1. `email-create` defaults to a draft. `--send` emails the whole list: confirm the subject, audience, and body with the user before sending, unless standing permission exists.
2. `subscriber-add` is a write: confirm the email address with the user first.
3. Reading (subscribers, emails) needs no confirmation.
4. The exact auth header is `Authorization: Token <key>` (never Bearer).
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/buttondown.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/buttondown.py

## Maturity
🧪 Draft: written from Buttondown's public API docs; not yet live-tested end-to-end.
