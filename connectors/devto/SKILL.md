---
name: "devto"
description: "Read and write dev.to: own profile, own articles (published, drafts, all), public articles by username, create and update articles with a safe draft default. Trigger phrases: dev.to, devto, blog post, publish article, draft article."
metadata: { "includeInPrompt": true }
tagline: "Read and write dev.to: own profile, own articles (published, drafts, all), public articles by username, create and update articles with a safe draft default."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["dev.to"]
---

# Dev.to

## Purpose
Read and write the user's dev.to account: own profile, own articles (published, unpublished drafts, or all), public articles by any username, create articles (draft by default), update articles. Use when the user mentions dev.to, a blog post, or publishing an article.

## Tooling
All commands go through `bin/devto.py`:

```bash
bin/devto.py me                                                      # verify the API key
bin/devto.py my-articles                                             # published articles
bin/devto.py my-articles --state all                                 # published + drafts
bin/devto.py articles-by-user --username ben                         # public reads, no key needed
bin/devto.py article-create --title "My post" --body-markdown "..." --tags "ai,python"  # draft by default
bin/devto.py article-create --title "My post" --body-file ./draft.md --tags "ai" --published  # confirm first: goes live
bin/devto.py article-update --id 123456 --title "New title"          # confirm first
```

## Auth
- Provider id: `devto` (credential is collected as `custom.devto`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created at dev.to under Settings > Account. The key is sent as a plain `api-key: <key>` header, verbatim, never as Bearer.
- Allowed hosts: `dev.to`
- Status check: `bin/devto.py me` (must return `"ok": true`)

## Operating Rules
1. `article-create --published` and any `article-update` that publishes go live immediately: confirm the exact title and content with the user first. Without `--published`, creates default to private drafts (`published: false`), which are safe to stage.
2. Reading (me, my-articles, articles-by-user) needs no confirmation.
3. Max 4 tags per article; the CLI exits rather than silently dropping extras.
4. Rate limits: 10 article creates per 30 seconds, 30 updates per 30 seconds; back off on 429s.
5. The API has no per-article view analytics; do not promise them.
6. Authenticated calls are server-side only (dev.to disables authenticated CORS), which matches how this CLI runs.
7. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/devto.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/devto.py

## Maturity
🧪 Draft: written from dev.to's public API docs via the verified research dossier; not yet live-tested end-to-end.
