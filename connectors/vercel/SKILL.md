---
name: "vercel"
description: "Inspect Vercel projects and deployments: your account, project list, recent deploys. Trigger phrases: vercel, vercel project, vercel deployment."
metadata: { "includeInPrompt": true }
tagline: "See your Vercel account, projects, and recent deployments."
catalog_auth: "personal token (per-user, vercel.com/account/tokens)"
catalog_hosts: ["api.vercel.com"]
---

# Vercel

## Purpose
Read-only visibility into the user's Vercel account: who the token belongs to, all projects, and recent deployments for a project. Use when the user asks about their Vercel projects, deploys, or site status.

## Tooling
All commands go through `bin/vercel.py`:

```bash
bin/vercel.py me                             # verify the connection (your user)
bin/vercel.py projects                       # list projects (name, framework)
bin/vercel.py deployments --project my-site  # recent deployments (url, state)
```

## Auth
- Provider id: `vercel` (credential is collected as `custom.vercel`)
- Collection: personal token from vercel.com/account/tokens via the secure credential flow (`credentials.request_api_access`)
- Connect placement: bearer_header
- Allowed hosts: `api.vercel.com`
- Status check: `bin/vercel.py me` (must return your user profile)

## Operating Rules
1. This skill is read-only by design: no deploy, delete, or env-var commands ship.
2. Reading needs no confirmation.
3. Tokens can be scoped to an account or a team; if calls return 403, the token's scope is wrong: ask the user to create one with the right scope.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/vercel.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/vercel.py

## Maturity
🧪 Draft: written from Vercel's public REST API docs; not yet live-tested end-to-end.
