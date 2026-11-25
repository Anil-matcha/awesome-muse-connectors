---
name: "airtable"
description: "List Airtable bases, read table records, and add records. Trigger phrases: airtable, my base, add a record, spreadsheet."
metadata: { "includeInPrompt": true }
tagline: "List Airtable bases, read table records, and add records."
catalog_auth: "Airtable personal access token (per-user, airtable.com/create/tokens)"
catalog_hosts: ["api.airtable.com"]
---

# Airtable

## Purpose
Work the user's Airtable: list bases (`bases`), read table records (`records`), and add a record (`create`).

## Tooling
All commands go through `bin/airtable.py`:

```bash
bin/airtable.py bases                                            # list bases (name, id)
bin/airtable.py records --base appABC --table "Tasks"            # read records (flattened fields), 10 max
bin/airtable.py records --base appABC --table "Tasks" --limit 50
bin/airtable.py create --base appABC --table "Tasks" --fields '{"Name": "Buy milk"}'
```

Use `bases` first to resolve a base name to its id (`app...`). The table name is the name shown in the base.

## Auth
- Provider id: `airtable` (credential is collected as `custom.airtable`)
- Collection: personal access token via the secure credential flow (`credentials.request_api_access`): create one at airtable.com/create/tokens with scopes `data.records:read`, `data.records:write`, and `schema.bases:read`, and grant it access to the bases you want to use
- Connect placement: `bearer_header`
- Allowed hosts: `api.airtable.com`
- Status check: `bin/airtable.py bases` (a successful list proves the token works)

## Operating Rules
1. `create` is a write: confirm the table and field values with the user before running, unless standing permission exists.
2. Reading (`bases`, `records`) needs no confirmation.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/airtable.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/airtable.py

## Maturity
🧪 Draft: written from Airtable's public Web API docs; not yet live-tested end-to-end.
