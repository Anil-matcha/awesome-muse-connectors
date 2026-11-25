---
name: "openai"
description: "Check OpenAI API access and list the models your key can use. Read-only. Trigger phrases: openai, openai models, what models do I have access to."
metadata: { "includeInPrompt": true }
tagline: "Check your OpenAI API access and list the models your key can use. Read-only."
catalog_auth: "OpenAI API key (per-user, platform.openai.com/api-keys)"
catalog_hosts: ["api.openai.com"]
---

# OpenAI

## Purpose
Check that the user's OpenAI API key works and list the models available to it (id and owner). Read-only by design: this skill never spends credits; it ships no completion, image, or other billable calls.

## Tooling
All commands go through `bin/openai.py`:

```bash
bin/openai.py models    # list models available to this key (id, owned_by), truncated to 40
```

## Auth
- Provider id: `openai` (credential is collected as `custom.openai`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`): create one at platform.openai.com/api-keys
- Connect placement: `bearer_header`
- Allowed hosts: `api.openai.com`
- Status check: `bin/openai.py models` (a successful list proves the key works)

## Operating Rules
1. This skill is read-only. `models` is the only command; it never creates completions or spends the user's credits.
2. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/openai.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/openai.py

## Maturity
🧪 Draft: written from OpenAI's public API reference; not yet live-tested end-to-end.
