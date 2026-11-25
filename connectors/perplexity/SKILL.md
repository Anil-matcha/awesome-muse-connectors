---
name: "perplexity"
description: "Read and write Perplexity: ask AI questions with web search and citations, list models, run raw searches. Trigger phrases: perplexity, sonar, ai search."
metadata: { "includeInPrompt": true }
tagline: "Ask questions with citations, search the web."
catalog_auth: "API key (per-user)"
catalog_hosts: ["api.perplexity.ai"]
---

# Perplexity

## Purpose
Ask Perplexity AI questions with live web search and citations. Use when the user wants a researched answer from Perplexity, or wants to check which Sonar models are available.

## Tooling
All commands go through `bin/perplexity.py`:

```bash
bin/perplexity.py auth                                                      # verify the API key
bin/perplexity.py models                                                    # list available models
bin/perplexity.py ask --model sonar --question "What is new in Python 3.13?"  # ask a question, get answer plus citations
bin/perplexity.py search --query "latest AI hardware news"                  # raw search results
```

Known models: `sonar`, `sonar-pro`, `sonar-reasoning`, `sonar-deep-research`. Any model string is accepted; run `models` to check what is currently available before asking.

## Auth
- Provider id: `perplexity` (credential is collected as `custom.perplexity`)
- Collection: API key (`pplx-...`) via the secure credential flow (`credentials.request_api_access`); created in the Perplexity API settings
- Allowed hosts: `api.perplexity.ai`
- Status check: `bin/perplexity.py auth` (must return `"ok": true`)

## Operating Rules
1. Reads (models, ask, search) need no confirmation.
2. The API rate-limits to roughly 50 requests per minute; back off on 429s.
3. Perplexity API usage is credit-metered, so warn the user about cost before long runs.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/perplexity.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/perplexity.py

## Maturity
🧪 Draft: written from Perplexity's public API docs; not yet live-tested end-to-end.
