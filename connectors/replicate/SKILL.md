---
name: "replicate"
description: "Read and write Replicate: look up model versions and input schemas, run predictions, poll status, cancel runs. Trigger phrases: replicate, ai models."
metadata: { "includeInPrompt": true }
tagline: "Run AI models, poll predictions."
catalog_auth: "API key (per-user)"
catalog_hosts: ["api.replicate.com"]
---

# Replicate

## Purpose
Run AI models on Replicate: look up a model to get its version ID and input schema, create an async prediction, poll its status, and cancel runs. Use when the user wants to run a specific model by `owner/name`.

## Tooling
All commands go through `bin/replicate.py`:

```bash
bin/replicate.py auth                                                  # verify the API key
bin/replicate.py model --name stability-ai/sdxl                        # get version ID and input schema
bin/replicate.py predict --version <version-id> --input-json '{"prompt": "..."}'  # start a prediction
bin/replicate.py status --id <prediction-id>                           # poll prediction status
bin/replicate.py cancel --id <prediction-id>                           # cancel a running prediction
```

Always call `model` first: copy the `latest_version_id` and match your `--input-json` to its `input_schema` before calling `predict`.

## Auth
- Provider id: `replicate` (credential is collected as `custom.replicate`)
- Collection: API token via the secure credential flow (`credentials.request_api_access`); created in the Replicate account settings
- Allowed hosts: `api.replicate.com`
- Status check: `bin/replicate.py auth` (must return `"ok": true`)

## Operating Rules
1. `predict` and `cancel` are writes: confirm the model, version, and input with the user before running, unless standing permission exists. Predictions cost money per run, so warn about cost too.
2. Predictions are async: after `predict`, poll `status` until the status reads `succeeded` or `failed`.
3. Output file URLs in a prediction expire after 1 hour; download anything worth keeping right away.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/replicate.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/replicate.py

## Maturity
🧪 Draft: written from Replicate's public API docs; not yet live-tested end-to-end.
