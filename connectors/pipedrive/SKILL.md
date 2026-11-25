---
name: "pipedrive"
description: "Read and write Pipedrive: list deals and contacts, create deals. Trigger phrases: pipedrive, my pipeline, deals."
metadata: { "includeInPrompt": true }
tagline: "List deals and contacts, create deals. CRM for your pipeline."
catalog_auth: "personal API token (per-user) + company subdomain"
catalog_hosts: ["{company}.pipedrive.com"]
---

# Pipedrive

## Purpose
Read and write the user's Pipedrive CRM: list deals, list contacts, create deals. Use when the user mentions Pipedrive, their pipeline, or deals.

## Tooling
All commands go through `bin/pipedrive.py`. Every command takes `--company` (your Pipedrive subdomain, e.g. `acme` for acme.pipedrive.com):

```bash
bin/pipedrive.py auth --company acme                      # verify the API token
bin/pipedrive.py deals --company acme --limit 25          # list deals
bin/pipedrive.py deals --company acme --status won        # filter by status
bin/pipedrive.py persons --company acme --limit 25       # list contacts
bin/pipedrive.py create-deal --company acme --title "New deal" --value 5000
```

## Auth
- Provider id: `pipedrive` (credential is collected as `custom.pipedrive`)
- Collection: personal API token via the secure credential flow (`credentials.request_api_access`); created in Pipedrive under Personal preferences > API. The company subdomain is passed per-command with `--company`, never stored.
- Allowed hosts: `{company}.pipedrive.com` (the user's own company subdomain only)
- Status check: `bin/pipedrive.py auth --company <subdomain>` (must return `"ok": true`)

## Operating Rules
1. `create-deal` is a write: confirm the title, value, and company with the user before creating, unless standing permission exists.
2. Reading (deals, persons) needs no confirmation.
3. The CLI only ever talks to the `--company` subdomain given on the command line; it refuses anything else.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/pipedrive.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/pipedrive.py

## Maturity
🧪 Draft: written from Pipedrive's public API docs; not yet live-tested end-to-end.
