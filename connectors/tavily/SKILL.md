---
name: "tavily"
description: "Fast, clean web research: search with an AI answer and cited sources. Trigger phrases: research this, web search, look up, tavily, find sources."
metadata: { "includeInPrompt": true }
tagline: "Fast, clean web research: one call returns an AI answer plus ranked sources with snippets. Read-only."
catalog_auth: "Tavily API key (per-user, tavily.com)"
catalog_hosts: ["api.tavily.com"]
---

# Tavily

## Purpose
Give any Muse fast, clean web research: one call returns an AI-generated answer plus ranked sources with snippets. Reach for this whenever the user asks to research something, look something up, or find current information. It beats raw browsing for quick factual grounding.

## Tooling
All commands go through `bin/tavily.py`:

```bash
bin/tavily.py search --query "who won the 2026 supernova challenge" --max-results 5
```

Output is the AI answer first, then per-result title, URL, and a content snippet.

## Auth
- Provider id: `tavily` (credential is collected as `custom.tavily`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`): a Tavily API key (tavily.com), pasted once into the hosted form
- Allowed hosts: `api.tavily.com`
- Status check: `bin/tavily.py search --query "test" --max-results 1` (must return an answer and results)

## Operating Rules
1. This skill is read-only: no confirmation needed, ever.
2. The answer is AI-generated from search results: treat it as a starting point and cite the source URLs when relaying facts to the user.
3. Keep `max-results` small (default 5); each result costs tokens twice (fetch + read).
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/tavily.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/tavily.py

## Maturity
🧪 Draft: written from Tavily's public API docs; not yet live-tested end-to-end.
