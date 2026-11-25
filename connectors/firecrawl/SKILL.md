---
name: "firecrawl"
description: "Scrape and crawl websites with Firecrawl: scrape a page, start a crawl, check crawl status, map a site, search the web. Trigger phrases: firecrawl, scrape website."
metadata: { "includeInPrompt": true }
tagline: "Scrape pages, crawl sites, search the web."
catalog_auth: "API key (per-user)"
catalog_hosts: ["api.firecrawl.dev"]
---

# Firecrawl

## Purpose
Turn websites into clean data with Firecrawl: scrape a single page to markdown, start an async crawl of a whole site, poll the crawl for results, map a site's URLs, and run web search. Use when the user mentions Firecrawl or asks to scrape a website.

## Tooling
All commands go through `bin/firecrawl.py`:

```bash
bin/firecrawl.py auth                                 # verify the API key (costs one map call)
bin/firecrawl.py scrape --url "https://example.com"   # scrape one page to markdown
bin/firecrawl.py crawl --url "https://example.com"    # start a crawl; returns a job id
bin/firecrawl.py crawl-status --id "abc123"           # poll a crawl job
bin/firecrawl.py map --url "https://example.com"      # list URLs on a site
bin/firecrawl.py search --query "ai pricing pages"    # web search
```

Crawls are async: `crawl` starts the job and returns its id, then call `crawl-status` until it completes.

## Auth
- Provider id: `firecrawl` (credential is collected as `custom.firecrawl`)
- Collection: API key (`fc-...`) via the secure credential flow (`credentials.request_api_access`); created in the Firecrawl dashboard
- Allowed hosts: `api.firecrawl.dev`
- Status check: `bin/firecrawl.py auth` (maps https://example.com; costs one credit)

## Operating Rules
1. Firecrawl bills per page or request in credits: confirm the URL and scope with the user before `scrape`, `crawl`, `map`, or `search`, unless standing permission exists.
2. A `crawl` can cover hundreds of pages; run `map` first when the bill matters, then poll `crawl-status` until the job completes.
3. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/firecrawl.py

## Maturity
🧪 Draft: written from Firecrawl's public API docs; not yet live-tested end-to-end.
