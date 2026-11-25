---
name: "cloudflare"
description: "Read Cloudflare zones and DNS records: list zones, list DNS records for a zone. Trigger phrases: cloudflare, dns records, cloudflare zone."
metadata: { "includeInPrompt": true }
tagline: "List your Cloudflare zones and read DNS records. Read-only."
catalog_auth: "API token (per-user, dash.cloudflare.com \u2192 My Profile \u2192 API Tokens; needs Zone:Read + DNS:Read)"
catalog_hosts: ["api.cloudflare.com"]
---

# Cloudflare

## Purpose
Read-only visibility into the user's Cloudflare account: list zones (domains) and read the DNS records for a zone. Use when the user asks about their domains, DNS, or Cloudflare setup.

## Tooling
All commands go through `bin/cloudflare.py`:

```bash
bin/cloudflare.py zones                 # list zones (name, status)
bin/cloudflare.py dns --zone ZONE_ID    # DNS records for a zone (type, name, content)
```

## Auth
- Provider id: `cloudflare` (credential is collected as `custom.cloudflare`)
- Collection: API token from dash.cloudflare.com → My Profile → API Tokens (needs `Zone:Read` and `DNS:Read` permissions) via the secure credential flow (`credentials.request_api_access`)
- Connect placement: bearer_header
- Allowed hosts: `api.cloudflare.com`
- Status check: `bin/cloudflare.py zones` (must return `"success": true`)

## Operating Rules
1. This skill is read-only by design: no DNS create/update/delete or cache-purge commands ship.
2. Reading needs no confirmation.
3. Cloudflare wraps every response in a `{"success", "result", "errors"}` envelope; the CLI unwraps `result` and surfaces `errors` on failure.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/cloudflare.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/cloudflare.py

## Maturity
🧪 Draft: written from Cloudflare's public API docs; not yet live-tested end-to-end.
