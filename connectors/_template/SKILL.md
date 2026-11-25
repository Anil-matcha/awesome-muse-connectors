---
name: "<provider-id>"
description: "<What it does, one line>. Trigger phrases: <phrases>."
metadata: { "includeInPrompt": true }
tagline: "<Human one-liner for the catalog table and site card>"
catalog_auth: "<Auth summary, e.g. API key (per-user)>"
catalog_hosts: ["<allowed host>"]
---

# <Display Name>

## Purpose
<What this connector does and when Muse should reach for it.>

## Tooling
<Exact CLI commands with copy-pasteable examples. Only documented commands exist.>
```bash
bin/<name>.py <command> [--flags]
```

## Auth
- Provider id: `<provider-id>` (credential is collected as `custom.<provider-id>`)
- Collection: <API key | provider OAuth> via the secure credential flow (`credentials.request_api_access`)
- Required scopes: <list>
- Allowed hosts: <host, host>
- Status check: `bin/<name>.py auth`

## Operating Rules
<Confirm-before-write rules, rate limits, things to never do.>

## Files
- SKILL.md
- bin/<name>.py

## Maturity
🧪 Draft
