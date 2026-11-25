---
name: "digitalocean"
description: "Inspect DigitalOcean: list droplets and domains. Trigger phrases: digitalocean, droplet, digitalocean domains."
metadata: { "includeInPrompt": true }
tagline: "List your DigitalOcean droplets and domains. Read-only."
catalog_auth: "personal access token (per-user, cloud.digitalocean.com \u2192 API)"
catalog_hosts: ["api.digitalocean.com"]
---

# DigitalOcean

## Purpose
Read-only visibility into the user's DigitalOcean account: list droplets (name, status, region) and domains. Use when the user asks what servers or domains they have on DigitalOcean.

## Tooling
All commands go through `bin/digitalocean.py`:

```bash
bin/digitalocean.py droplets   # droplets (name, status, region)
bin/digitalocean.py domains    # domains (name)
```

## Auth
- Provider id: `digitalocean` (credential is collected as `custom.digitalocean`)
- Collection: personal access token from cloud.digitalocean.com → API → Personal access tokens, via the secure credential flow (`credentials.request_api_access`)
- Connect placement: bearer_header
- Allowed hosts: `api.digitalocean.com`
- Status check: `bin/digitalocean.py droplets` (must return your droplets)

## Operating Rules
1. This skill is read-only by design: no droplet create/delete/action commands ship.
2. Reading needs no confirmation.
3. DigitalOcean tokens support scopes; a read-only token (`droplet:read`, `domain:read`) is enough for this skill.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/digitalocean.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/digitalocean.py

## Maturity
🧪 Draft: written from DigitalOcean's public API docs; not yet live-tested end-to-end.
