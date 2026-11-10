---
name: "groq"
description: "Groq chat completions on the OpenAI-compatible API — fast open-model inference — plus model listing. Trigger phrases: groq, groq chat, fast inference, gpt-oss."
metadata: { "includeInPrompt": true }
tagline: "Groq chat completions on the OpenAI-compatible API — fast open-model inference (gpt-oss, Llama, Qwen) plus model listing. Read-only inference."
catalog_auth: "API key (per-user) via the secure credential flow"
catalog_hosts: ["api.groq.com"]
---

# Groq

## Purpose
Run chat completions on Groq's OpenAI-compatible API — very fast inference for open models — and list the models the key can access. Use when the user asks for Groq, needs a fast/cheap completion lane, or wants a model-routing fallback.

Source: Groq API documentation (console.groq.com/docs), checked 2026-10-19.

## Tooling
All commands go through `bin/groq_call.py`:

```bash
bin/groq_call.py auth                                        # status check: verify the credential answers
bin/groq_call.py models                                      # list available model ids
bin/groq_call.py chat --model openai/gpt-oss-20b --prompt "..." [--system "..."] [--max-tokens N] [--temperature T]
```

## Auth
- Provider id: `groq` (credential is collected as `custom.groq`)
- Collection: API key from console.groq.com/keys, via the secure credential flow (`credentials.request_api_access`)
- Connect placement: bearer_header
- Allowed hosts: `api.groq.com`
- Status check: `bin/groq_call.py auth` (must return `"ok": true`)

## Operating Rules
1. Inference only: this connector reads the model list and runs completions; it manages nothing. A chat call consumes the key's rate limits/usage — that is its purpose.
2. Groq retires model ids without much ceremony (for example `llama-3.3-70b-versatile` now returns 404 `model_not_found`). Run `models` before assuming an id exists, and treat a 404 as a stale id, not an auth failure.
3. Groq sits behind Cloudflare, which blocks urllib's default User-Agent with error 1010. The CLI sends a browser User-Agent on every request; keep that header if you modify it.
4. A 401/403 is a question about the request before it is a question about the key — confirm the surrogate was attached. Never print, log, or persist the raw key; the CLI only ever handles surrogates.

## Files
- SKILL.md
- bin/groq_call.py

## Maturity
✅ Live — this is the production version from a running Muse setup: chat completions run daily as a fast classification/inference lane in a multi-provider routing pool. Live-tested 2026-10-19 (default model `openai/gpt-oss-20b` verified answering).
