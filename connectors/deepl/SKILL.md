---
name: "deepl"
description: "Translate text with DeepL: translate between 30+ languages, list languages, check usage. Trigger phrases: deepl, translate this."
metadata: { "includeInPrompt": true }
tagline: "Translate text between 30+ languages, check usage."
catalog_auth: "API key (per-user; free keys use api-free.deepl.com, paid keys use api.deepl.com)"
catalog_hosts: ["api-free.deepl.com", "api.deepl.com"]
---

# DeepL

## Purpose
Translate text with DeepL: translate between 30+ languages with optional formality control, list supported languages, check character usage. Use when the user mentions DeepL or wants text translated.

## Tooling
All commands go through `bin/deepl.py`:

```bash
bin/deepl.py auth                                        # verify the key and show usage
bin/deepl.py translate --text "Hello" --target-lang FR  # translate text
bin/deepl.py translate --text "Hello" --target-lang DE --source-lang EN --formality more
bin/deepl.py languages                                  # list supported target languages
```

Free-plan keys end in `:fx` and use `api-free.deepl.com` (the default). Paid keys use `api.deepl.com`: pass `--host api.deepl.com` for those.

## Auth
- Provider id: `deepl` (credential is collected as `custom.deepl`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in the DeepL account under API Keys
- Allowed hosts: `api-free.deepl.com`, `api.deepl.com`
- Status check: `bin/deepl.py auth` (must return `"ok": true`)

## Operating Rules
1. Translation is a read-like operation: no confirmation needed, but usage counts against the user's character quota, so keep batches reasonable.
2. Machine translation can be wrong: flag this when the output will be published or used in legal, medical, or brand contexts.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/deepl.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/deepl.py

## Maturity
🧪 Draft: written from DeepL's public API docs; not yet live-tested end-to-end.
