---
name: "newsapi"
description: "Top headlines and full-text news search. Trigger phrases: news, headlines, newsapi."
metadata: { "includeInPrompt": true }
tagline: "Top headlines and full-text news search. Read-only."
catalog_auth: "NewsAPI key (per-user, newsapi.org/register; free tier 100 requests/day)"
catalog_hosts: ["newsapi.org"]
---

# NewsAPI

## Purpose
Read-only news: top headlines by country and full-text search across news articles. Use when the user asks for news, headlines, or mentions NewsAPI.

## Tooling
All commands go through `bin/newsapi.py`:

```bash
bin/newsapi.py headlines --country us --limit 10      # top headlines
bin/newsapi.py search --query "spacex" --limit 10      # search all news
```

## Auth
- Provider id: `newsapi` (credential is collected as `custom.newsapi`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Get a key: newsapi.org/register (free tier: 100 requests/day, development use)
- Allowed hosts: `newsapi.org`
- Status check: `bin/newsapi.py headlines --country us --limit 1`
- Connect placement: `query_param:apiKey`

Note: NewsAPI also accepts the key in an `X-Api-Key` header, but this connector uses the `apiKey` query param for helper compatibility.

## Operating Rules
1. This connector is read-only: it only reads news. It never writes, modifies, or sends anything on the user's behalf.
2. The `--country` flag takes a 2-letter country code (e.g. `us`, `gb`, `ng`); `headlines` defaults to `us`.
3. Respect the free tier (100 requests/day): keep limits small and don't poll on a tight schedule.
4. NewsAPI returns `{"status": "error", ...}` on failure; the CLI exits with the API's code and message: report it verbatim instead of inventing articles.
5. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/newsapi.py

## Maturity
🧪 Draft: written from NewsAPI's public docs; not yet live-tested end-to-end.
