---
name: "huggingface"
description: "Verify your Hugging Face account and search the model hub. Read-only. Trigger phrases: hugging face, huggingface, hf model, search models."
metadata: { "includeInPrompt": true }
tagline: "Verify your Hugging Face account and search the model hub. Read-only."
catalog_auth: "Hugging Face user access token (per-user, huggingface.co/settings/tokens)"
catalog_hosts: ["huggingface.co"]
---

# Hugging Face

## Purpose
Verify the user's Hugging Face account and search the public model hub: whoami (name, email), and model search by keyword with likes/downloads. Read-only: no repo writes ship in this skill.

## Tooling
All commands go through `bin/huggingface.py`:

```bash
bin/huggingface.py me                        # whoami: name, email, account type
bin/huggingface.py models --query llama      # search the model hub (id, likes, downloads), 10 results
```

## Auth
- Provider id: `huggingface` (credential is collected as `custom.huggingface`)
- Collection: user access token via the secure credential flow (`credentials.request_api_access`): create one at huggingface.co/settings/tokens (a fine-grained read token is enough)
- Connect placement: `bearer_header`
- Allowed hosts: `huggingface.co`
- Status check: `bin/huggingface.py me` (a successful whoami proves the token works)

## Operating Rules
1. This skill is read-only. No repository creation, upload, or delete commands ship.
2. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/huggingface.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/huggingface.py

## Maturity
🧪 Draft: written from Hugging Face's public Hub API docs; not yet live-tested end-to-end.
