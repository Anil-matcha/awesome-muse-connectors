---
name: "render"
description: "Inspect Render services and deploys: list services, list recent deploys. Trigger phrases: render, render service, render deploy."
metadata: { "includeInPrompt": true }
tagline: "List your Render services and recent deploys. Read-only."
catalog_auth: "API key (per-user, dashboard.render.com \u2192 Account Settings \u2192 API Keys)"
catalog_hosts: ["api.render.com"]
---

# Render

## Purpose
Read-only visibility into the user's Render account: list services and inspect recent deploys for a service. Use when the user asks what's running on Render or whether a deploy succeeded.

## Tooling
All commands go through `bin/render.py`:

```bash
bin/render.py services                       # list services (name, type, region)
bin/render.py deploys --service srv-abc123   # recent deploys (status, created)
```

## Auth
- Provider id: `render` (credential is collected as `custom.render`)
- Collection: API key from dashboard.render.com → Account Settings → API Keys, via the secure credential flow (`credentials.request_api_access`)
- Connect placement: bearer_header
- Allowed hosts: `api.render.com`
- Status check: `bin/render.py services` (must return your services)

## Operating Rules
1. This skill is read-only by design: no deploy, suspend, restart, or env-var commands ship.
2. Reading needs no confirmation.
3. A Render API key can see every workspace the account belongs to; the key's reach is the account's reach.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/render.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/render.py

## Maturity
🧪 Draft: written from Render's public API docs; not yet live-tested end-to-end.
