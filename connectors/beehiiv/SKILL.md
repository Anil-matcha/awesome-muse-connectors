---
name: "beehiiv"
description: "Read and write beehiiv: list publications, subscribers, and posts; add subscribers. Trigger phrases: beehiiv, newsletter subscribers."
metadata: { "includeInPrompt": true }
tagline: "List publications, subscribers, and posts; add subscribers."
catalog_auth: "API key (per-user; Scale plan or higher)"
catalog_hosts: ["api.beehiiv.com"]
---

# Beehiiv

## Purpose
Read and write the user's beehiiv newsletters: list publications, list subscribers, list posts with stats, add subscribers. Use when the user mentions beehiiv or their newsletter.

## Tooling
All commands go through `bin/beehiiv.py`:

```bash
bin/beehiiv.py auth                                     # verify the API key
bin/beehiiv.py publications                             # list publications
bin/beehiiv.py subscriptions --pub pub_abc123 --limit 25  # list subscribers
bin/beehiiv.py posts --pub pub_abc123 --limit 25        # list posts with stats
bin/beehiiv.py subscribe --pub pub_abc123 --email "them@example.com"  # add a subscriber
```

Most endpoints need a publication ID (`pub_...`); use `publications` to resolve it first.

## Auth
- Provider id: `beehiiv` (credential is collected as `custom.beehiiv`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in beehiiv under Settings > Workspace Settings > API (requires Owner or Admin role, Scale plan or higher)
- Allowed hosts: `api.beehiiv.com`
- Status check: `bin/beehiiv.py auth` (must return `"ok": true`)

## Operating Rules
1. `subscribe` is a write: confirm the email address and publication with the user before adding, unless standing permission exists.
2. Reading (publications, subscriptions, posts) needs no confirmation.
3. beehiiv rate-limits to 180 requests per minute per organization; back off on 429s.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/beehiiv.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/beehiiv.py

## Maturity
🧪 Draft: written from beehiiv's public API docs; not yet live-tested end-to-end.
