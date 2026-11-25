---
name: "kit"
description: "Read and write Kit (ConvertKit): list subscribers, broadcasts, sequences, tags; draft broadcasts. Trigger phrases: kit, convertkit, newsletter, broadcasts, subscribers."
metadata: { "includeInPrompt": true }
tagline: "Read and write Kit (ConvertKit): list subscribers, broadcasts, sequences, tags; draft broadcasts."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.kit.com"]
---

# Kit

## Purpose
Read and write the user's Kit (formerly ConvertKit) account: list subscribers, broadcasts, sequences, and tags; create broadcast drafts. Use when the user mentions Kit, ConvertKit, or their newsletter.

## Tooling
All commands go through `bin/kit.py`:

```bash
bin/kit.py auth                                              # verify the API key
bin/kit.py subscribers --limit 25                            # list subscribers
bin/kit.py broadcasts --limit 25                             # list broadcasts
bin/kit.py broadcast-create --subject "Hi" --content "..."   # create a broadcast draft
bin/kit.py broadcast-create --subject "Hi" --content "..." --send  # send to the list (confirm first)
bin/kit.py sequences --limit 25                              # list sequences
bin/kit.py tags --limit 25                                   # list tags
```

## Auth
- Provider id: `kit` (credential is collected as `custom.kit`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in Kit under Settings > Advanced > API secret (keys look like `kit_...`)
- Allowed hosts: `api.kit.com`
- Status check: `bin/kit.py auth` (must return `"ok": true`)

## Operating Rules
1. `broadcast-create` defaults to a draft. `--send` emails the list: confirm the subject, audience, and content with the user before sending, unless standing permission exists.
2. Adding subscribers to sequences that email them is confirmation-gated.
3. Reading (subscribers, broadcasts, sequences, tags) needs no confirmation.
4. Rate limits: 120 requests per 60 seconds with an API key, 600 per 60 seconds with OAuth; back off on 429s.
5. The exact auth header is `X-Kit-Api-Key` (never Bearer).
6. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/kit.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/kit.py

## Maturity
🧪 Draft: written from Kit's public v4 API docs; not yet live-tested end-to-end.
