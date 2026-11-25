---
name: "apollo"
description: "Search B2B contacts with Apollo.io: find people by title and company, enrich contacts and companies. Trigger phrases: apollo, find prospects, enrich contact."
metadata: { "includeInPrompt": true }
tagline: "Search B2B contacts and enrich people and companies."
catalog_auth: "API key (per-user; Professional plan or higher)"
catalog_hosts: ["api.apollo.io"]
---

# Apollo

## Purpose
Search B2B contacts with Apollo.io: search people by title, location, and company; enrich a person or a company. Use when the user mentions Apollo, prospecting, or wants contact/company data enriched.

## Tooling
All commands go through `bin/apollo.py`:

```bash
bin/apollo.py auth                                      # verify the API key
bin/apollo.py search --titles "VP Sales" --domains "acme.com" --limit 10  # search people
bin/apollo.py enrich --email "jane@acme.com"            # enrich one person (uses credits)
bin/apollo.py org-enrich --domain "acme.com"            # enrich one company
```

## Auth
- Provider id: `apollo` (credential is collected as `custom.apollo`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in Apollo under Settings > Integrations > API
- Allowed hosts: `api.apollo.io`
- Status check: `bin/apollo.py auth` (must return `"ok": true`)

## Operating Rules
1. `search` is free and needs no confirmation.
2. `enrich` and `org-enrich` consume Apollo credits: tell the user before running them on more than a single record, unless standing permission exists.
3. Apollo API access requires a Professional plan or higher; on lower plans the API returns errors: tell the user rather than retrying.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/apollo.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/apollo.py

## Maturity
🧪 Draft: written from Apollo's public API docs; not yet live-tested end-to-end.
