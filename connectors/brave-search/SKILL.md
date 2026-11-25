---
name: "brave-search"
description: "Independent web search from Brave's own index. Trigger phrases: brave, brave search, web search."
metadata: { "includeInPrompt": true }
tagline: "Independent web search from Brave's own index. Read-only."
catalog_auth: "Brave Search API key (per-user, brave.com/search/api; free tier 2,000 queries/month)"
catalog_hosts: ["api.search.brave.com"]
---

# Brave Search

## Purpose
Read-only web search powered by Brave's own independent index. Use when the user mentions Brave or asks for a web search.

## Tooling
All commands go through `bin/brave-search.py`:

```bash
bin/brave-search.py auth                                  # verify the connection
bin/brave-search.py search --query "AI agent frameworks" --count 10   # web search
```

## Auth
- Provider id: `brave-search` (credential is collected as `custom.brave-search`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Get a key: brave.com/search/api (free tier: 2,000 queries/month)
- Allowed hosts: `api.search.brave.com`
- Status check: `bin/brave-search.py auth` (must return `"ok": true`)
- Connect placement: `custom_header:X-Subscription-Token`

## Operating Rules
1. This connector is read-only: it only searches the web. It never writes, modifies, or sends anything on the user's behalf.
2. The `--count` parameter is clamped to 1-20 by the CLI; keep it at 10 or fewer unless the user asks for more, to conserve the 2,000 queries/month free tier.
3. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/brave-search.py

## Maturity
🧪 Draft: written from Brave Search's public API docs; not yet live-tested end-to-end.
