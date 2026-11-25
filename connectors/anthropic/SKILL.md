---
name: "anthropic"
description: "Check Anthropic API access and list available Claude models. Read-only. Trigger phrases: anthropic, claude models, anthropic api."
metadata: { "includeInPrompt": true }
tagline: "Check your Anthropic API access and list available Claude models. Read-only."
catalog_auth: "Anthropic API key (per-user, console.anthropic.com)"
catalog_hosts: ["api.anthropic.com"]
---

# Anthropic

## Purpose
Check that the user's Anthropic API key works and list the models available to it (id, display name). Read-only by design: this skill never spends credits; it ships no message, token-count, or other billable calls.

## Tooling
All commands go through `bin/anthropic.py`:

```bash
bin/anthropic.py models    # list models available to this key (id, display_name)
```

## Auth
- Provider id: `anthropic` (credential is collected as `custom.anthropic`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`): create one at console.anthropic.com
- Connect placement: `custom_header:x-api-key` (Anthropic uses `x-api-key`, not `Authorization: Bearer`)
- Allowed hosts: `api.anthropic.com`
- Status check: `bin/anthropic.py models` (a successful list proves the key works)

Note: every request also carries the required `anthropic-version: 2023-06-01` header, set by `bin/anthropic.py`.

## Operating Rules
1. This skill is read-only. `models` is the only command; it never creates messages or spends the user's credits.
2. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/anthropic.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/anthropic.py

## Maturity
🧪 Draft: written from Anthropic's public API docs; not yet live-tested end-to-end.
