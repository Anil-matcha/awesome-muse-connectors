---
name: "exa"
description: "Neural web search with page text: one call returns ranked sources with snippets. Trigger phrases: exa, exa search, search the web."
metadata: { "includeInPrompt": true }
tagline: "Neural web search with page text: one call returns ranked sources with snippets. Read-only."
catalog_auth: "Exa API key (per-user, dashboard.exa.ai/api-keys)"
catalog_hosts: ["api.exa.ai"]
---

# Exa

## Purpose
Read-only neural web search over Exa's index: one call returns ranked sources, and can also fetch each result's page text so the user gets snippets with substance. Use when the user mentions Exa or asks to search the web with ranked sources.

## Tooling
All commands go through `bin/exa.py`:

```bash
bin/exa.py auth                            # verify the connection
bin/exa.py search --query "Moltbook API" --limit 5   # search with page text
```

## Auth
- Provider id: `exa` (credential is collected as `custom.exa`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Get a key: dashboard.exa.ai/api-keys
- Allowed hosts: `api.exa.ai`
- Status check: `bin/exa.py auth` (must return `"ok": true`)
- Connect placement: `custom_header:x-api-key`

## Operating Rules
1. This connector is read-only: it only searches and fetches page text. It never writes, modifies, or sends anything on the user's behalf.
2. The search endpoint returns up to the requested `numResults`; keep `--limit` small (5 or fewer) unless the user asks for more, to conserve quota.
3. Returned `text` snippets are raw page content; quote them, do not invent facts beyond them.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/exa.py

## Maturity
🧪 Draft: written from Exa's public API docs; not yet live-tested end-to-end.
