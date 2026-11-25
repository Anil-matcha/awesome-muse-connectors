---
name: "mistral"
description: "Mistral AI (La Plateforme) API: chat completions, embeddings, document OCR, and model listing via api.mistral.ai. Trigger phrases: mistral, La Plateforme, mistral chat, mistral ocr, mistral embeddings."
metadata: { "includeInPrompt": true }
tagline: "Mistral AI's La Plateforme API: chat completions, embeddings, document OCR, and model listing via Bearer API key."
catalog_auth: "API key (per-user)"
catalog_hosts: ["api.mistral.ai"]
---

# Mistral AI

## Purpose
Call Mistral's La Plateforme API: run chat completions on Mistral models, create text embeddings, extract text and markdown from documents and images with the dedicated OCR endpoint, and list the models available to the API key. Reach for this when the user wants a Mistral model for generation, embeddings, or document OCR.

## Install
Copy, paste to your Muse:

```
Install this connector: https://raw.githubusercontent.com/bluman1/muse-connectors/main/connectors/mistral/SKILL.md
You are Muse. Fetch the URL above: it is a connector skill's SKILL.md.
1. Read its `## Files` manifest and download every listed file from the same directory (replace SKILL.md in the URL with each relative path).
2. Save them under ~/workspace/skills/mistral/, preserving paths. Compile any bin/*.py with python3 -m py_compile.
3. Follow the skill's `## Auth` section: connect my account via your secure credential flow (credentials.request_api_access) for the provider id it names.
4. Run the skill's status check and report what the connector can now do.
Never ask me for raw API keys or secrets in chat.
```

## Tooling
All commands go through `bin/mistral.py`:

```bash
bin/mistral.py auth                                              # verify the API key
bin/mistral.py models                                            # list models for this key
bin/mistral.py chat --prompt "Explain RAG in one paragraph"      # chat completion (bills credits)
bin/mistral.py chat --model mistral-medium-latest --system "You are terse." \
    --prompt "Summarize this: ..." --temperature 0.3 --max-tokens 300 --json-mode
bin/mistral.py embeddings --text "First chunk" --text "Second chunk"   # embeddings (bills credits)
bin/mistral.py embeddings --text "One line" --full                # print complete vectors
bin/mistral.py ocr --document-url https://example.com/doc.pdf     # OCR a PDF (billed per page)
bin/mistral.py ocr --image-url https://example.com/scan.png --include-images
```

Chat reads a single user prompt per call (plus an optional system prompt). For multi-turn conversation, pass the whole history as the prompt or extend the CLI.

## Auth
- Provider id: `mistral` (credential is collected as `custom.mistral`)
- Collection: API key (console.mistral.ai > API keys) via the secure credential flow (`credentials.request_api_access`)
- Auth scheme: `Authorization: Bearer <api key>` on every request
- Allowed hosts: `api.mistral.ai`
- Status check: `bin/mistral.py auth`

## Operating Rules
1. **Every billed call costs money.** These are ordinary API calls rather than third-party actions, so no `--confirm` gate applies, but surface the expected cost before running anything expensive. Chat and embeddings draw down the key's credit balance. OCR is billed per page processed.
2. **Model ids change.** Treat any named model id in examples (`mistral-large-latest`, `mistral-ocr-latest`, and the like) as provisional. Run `bin/mistral.py models` to see the ids this key can actually use, and pass the live id explicitly when a call fails with a model error.
3. **Do not fabricate model capabilities.** Magistral and other reasoning models return thinking-trace content blocks; the `chat` command returns the response text as-is. Do not invent fields or capabilities the API did not return.
4. **OCR documents are third-party content.** When OCRing a URL, prefer documents the user supplied or that are plainly public; do not exfiltrate the resulting markdown anywhere except the task that asked for it.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/mistral.py`). Do not print, log, or transmit the API key.
6. Honesty flags: no live API key was available while building this connector. Endpoint paths (`/v1/models`, `/v1/chat/completions`, `/v1/embeddings`, `/v1/ocr`), the Bearer auth scheme, and all request/response field names were taken from Mistral's public docs and third-party SDK references rather than a live call. The CLI surfaces Mistral's own error if anything differs. Model ids were cross-checked against docs and recent community references dated September 2026 and may have changed since. OCR options (`pages`, `include_image_base64`, `image_limit`, `image_min_size`) are confirmed in the docs but were not exercised against a live key. Mistral offers an Experiment (free-tier) plan on console.mistral.ai; its rate limits and quotas were not verified during this build.

## Files
- SKILL.md
- bin/mistral.py

## Maturity
🧪 Draft: written from Mistral's public docs and SDK examples; not yet live-tested end-to-end.
