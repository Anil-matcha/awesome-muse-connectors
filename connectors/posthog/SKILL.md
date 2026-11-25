---
name: "posthog"
description: "Read PostHog analytics: your user, projects, saved insights. Trigger phrases: posthog, analytics, posthog insights."
metadata: { "includeInPrompt": true }
tagline: "Your PostHog user, projects, and saved insights. Read-only."
catalog_auth: "personal API key (per-user, PostHog Settings \u2192 Personal API keys; starts `phx_`)"
catalog_hosts: ["configurable", "default app.posthog.com"]
---

# PostHog

## Purpose
Read-only access to the user's PostHog analytics: who the key belongs to, project list, and saved insights. Use when the user asks about their product analytics, funnels, or saved PostHog insights.

## Tooling
All commands go through `bin/posthog.py`. The API host is configurable with the global `--host` (default `app.posthog.com`):

```bash
bin/posthog.py me                          # verify the connection
bin/posthog.py projects                    # list projects
bin/posthog.py insights --project 123      # saved insights in a project
bin/posthog.py --host eu.posthog.com me    # EU-cloud users
```

## Auth
- Provider id: `posthog` (credential is collected as `custom.posthog`)
- Collection: personal API key (starts `phx_`) from PostHog → Settings → Personal API keys (scopes `query:read` and `project:read` suffice), via the secure credential flow (`credentials.request_api_access`)
- Connect placement: bearer_header
- Allowed hosts: configurable via `--host`; default `app.posthog.com`
- Status check: `bin/posthog.py me` (must return your user)

## Operating Rules
1. This skill is read-only by design: no insight create/update commands ship.
2. Reading needs no confirmation.
3. Use the app/management host (`app.posthog.com`, `us.posthog.com`, `eu.posthog.com`): never the ingestion host (`us.i.posthog.com` / `eu.i.posthog.com`), which serves a different API.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/posthog.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/posthog.py

## Maturity
🧪 Draft: written from PostHog's public API docs; not yet live-tested end-to-end.
