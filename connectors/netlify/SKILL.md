---
name: "netlify"
description: "Inspect Netlify sites and deploys: list sites, list recent deploys. Trigger phrases: netlify, netlify site, netlify deploy."
metadata: { "includeInPrompt": true }
tagline: "List your Netlify sites and recent deploys. Read-only."
catalog_auth: "personal access token (per-user, app.netlify.com \u2192 User settings \u2192 Applications)"
catalog_hosts: ["api.netlify.com"]
---

# Netlify

## Purpose
Read-only visibility into the user's Netlify account: list sites and inspect recent deploys for a site. Use when the user asks about their Netlify sites or whether a deploy succeeded.

## Tooling
All commands go through `bin/netlify.py`:

```bash
bin/netlify.py sites                    # sites (name, url, deploy state)
bin/netlify.py deploys --site SITE_ID   # recent deploys (state, created)
```

Find a site's ID in Site settings → General → Site details → API ID.

## Auth
- Provider id: `netlify` (credential is collected as `custom.netlify`)
- Collection: personal access token from app.netlify.com → User settings → Applications → Personal access tokens, via the secure credential flow (`credentials.request_api_access`)
- Connect placement: bearer_header
- Allowed hosts: `api.netlify.com`
- Status check: `bin/netlify.py sites` (must return your sites)

## Operating Rules
1. This skill is read-only by design: no deploy, rollback, or env-var commands ship.
2. Reading needs no confirmation.
3. Sites are identified by site ID, not domain name; use `sites` to resolve one first.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/netlify.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/netlify.py

## Maturity
🧪 Draft: written from Netlify's public API docs; not yet live-tested end-to-end.
