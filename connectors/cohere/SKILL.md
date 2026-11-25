---
name: "cohere"
description: "Cohere chat, embeddings, and reranking (Command, Embed, Rerank models) via the Cohere API. Trigger phrases: cohere, command model, rerank, embeddings."
metadata: { "includeInPrompt": true }
tagline: "Cohere chat, embeddings, and reranking (Command models) via the Cohere API. Read-only inference."
catalog_auth: "API key (per-user) via the secure credential flow"
catalog_hosts: ["api.cohere.com"]
---

# Cohere

## Purpose
Use Cohere's public API (v2) for chat completions with Command models, text embeddings, and document reranking, plus model listing. Use when the user asks for Cohere specifically, needs embeddings or a reranker, or wants another provider lane for routing and comparison.

Source: Cohere API documentation (docs.cohere.com), checked 2026-10-19.

## Tooling
All commands go through `bin/cohere_call.py`:

```bash
bin/cohere_call.py auth                                       # status check: verify the credential answers
bin/cohere_call.py models                                     # list available model names
bin/cohere_call.py chat --model command-a-03-2025 --prompt "..." [--system "..."]
bin/cohere_call.py embed --text "..." [--text "..."] [--input-type search_document|search_query|classification|clustering] [--show-first]
bin/cohere_call.py rerank --query "..." --doc "..." [--doc "..."] [--top-n N]
```

Chat response text lives in `message.content[]` entries of type `text`; the CLI extracts and prints it. `embed` prints vector count and dimensions (full vectors are large; `--show-first` shows the first 8 dimensions of the first vector as a sanity check).

## Auth
- Provider id: `cohere` (credential is collected as `custom.cohere`)
- Collection: API key from dashboard.cohere.com/api-keys, via the secure credential flow (`credentials.request_api_access`)
- Connect placement: bearer_header
- Allowed hosts: `api.cohere.com`
- Status check: `bin/cohere_call.py auth` (must return `"ok": true`)

## Operating Rules
1. Inference only: this connector reads the model list and runs chat/embed/rerank calls; it manages nothing. Calls consume the key's usage — that is their purpose.
2. Trial keys are heavily rate-limited and cannot use every model; a 403 on a specific model usually means the key tier, not a broken credential. Check `models` and the error body before concluding auth is broken.
3. Match `embed --input-type` to the job (documents vs queries) — mixing them silently degrades retrieval quality.
4. A 401/403 is a question about the request before it is a question about the key — confirm the surrogate was attached. Never print, log, or persist the raw key; the CLI only ever handles surrogates.

## Files
- SKILL.md
- bin/cohere_call.py

## Maturity
✅ Live — this is the production version from a running Muse setup: chat completions run daily as an inference lane in a multi-provider routing pool (default model `command-a-03-2025` verified answering); embed and rerank follow the same public v2 API surface. Live-tested 2026-10-19.
