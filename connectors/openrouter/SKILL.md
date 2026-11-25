---
name: "openrouter"
description: "OpenRouter chat completions, the full model catalog with pricing, and key usage/limit reporting. Trigger phrases: openrouter, model prices, openrouter key, chat completion."
metadata: { "includeInPrompt": true }
tagline: "OpenRouter chat completions plus the model catalog (names, prompt and completion pricing, free-model filter) and key usage/limit reporting."
catalog_auth: "API key (per-user) via the secure credential flow"
catalog_hosts: ["openrouter.ai"]
---

# OpenRouter

## Purpose
Work with OpenRouter through its public API: run chat completions against hundreds of hosted models, browse the model catalog with names and per-token pricing (prompt and completion), filter for free models, and check the connected key's label, usage, and limit. Use when the user asks to run a model through OpenRouter, compare model prices, find a free model, or check key spend.

Source: OpenRouter API documentation (openrouter.ai/docs), checked 2026-10-19.

## Tooling
All commands go through `bin/openrouter.py`:

```bash
bin/openrouter.py key                                        # status check: key label, usage, limit
bin/openrouter.py models [--free-only] [--filter substr] [--limit N]   # catalog (public, unauthenticated)
bin/openrouter.py chat --model <model-id> --prompt "..." [--system "..."] [--max-tokens N] [--temperature T]
```

## Auth
- Provider id: `openrouter` (credential is collected as `custom.openrouter`)
- Collection: API key from openrouter.ai/keys, via the secure credential flow (`credentials.request_api_access`)
- Connect placement: bearer_header
- Allowed hosts: `openrouter.ai`
- Status check: `bin/openrouter.py key` (must return your key's label and usage)

## Operating Rules
1. The previous catalog version of this connector was read-only; this production version also runs `chat` completions, because model routing is what the connector is for. A chat call spends the key's balance (or free-tier quota) — that is its purpose, not a side effect to confirm each time, but say which model ran and watch `key` usage on metered keys.
2. `models` is a public endpoint and is called **without** the credential attached — never send a key where it isn't needed. (The earlier catalog draft attached the credential to this public call; this version removes that.)
3. Model ids and availability change constantly; check `models` before assuming an id works. A `:free` variant can return 404 "unavailable for free" on accounts without credit history even when listed — keep a known-good free fallback and verify with a real call before relying on one.
4. A 401 is a question about the request before it is a question about the key — confirm the surrogate was attached. Never print, log, or persist the raw key; the CLI only ever handles surrogates.

## Files
- SKILL.md
- bin/openrouter.py

## Maturity
✅ Live — this is the production version from a running Muse setup: chat completions and the model catalog run daily as part of a multi-provider model-routing pool; the `key` and enriched `models` commands were merged from the earlier catalog draft and verified against the real API. Live-tested 2026-10-19.
