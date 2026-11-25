---
name: "attio"
description: "Read and write Attio: list objects, query records, upsert records, add notes and tasks. Trigger phrases: attio, crm."
metadata: { "includeInPrompt": true }
tagline: "Query CRM records, upsert by matching attribute, add notes and tasks."
catalog_auth: "API key (per-workspace)"
catalog_hosts: ["api.attio.com"]
---

# Attio

## Purpose
Read and write the user's Attio CRM: list objects, query records on any object, create-or-update records, add notes and tasks to records. Use when the user mentions Attio or their CRM.

## Tooling
All commands go through `bin/attio.py`:

```bash
bin/attio.py auth                                     # verify the API key
bin/attio.py objects                                  # list available objects
bin/attio.py query --object-slug companies --filter-json '{"filters":[]}'  # query records
bin/attio.py upsert --object-slug companies --match-attribute email --values-json '{"name":[{"value":"Acme"}],"email":[{"value":"a@acme.com"}]}'  # create or update a record
bin/attio.py note --record-id rec_abc123 --title "Call notes" --content "Discussed pricing"  # add a note
bin/attio.py task --record-id rec_abc123 --title "Send proposal"  # add a task
```

Attio's preferred write path is `upsert`: it creates the record when `matching_attribute` matches nothing, and updates the matched record otherwise.

Attribute values are arrays even for scalar fields: every attribute value is sent as a list of objects, like `[{"value": 42}]` or `[{"value": "Acme"}]`. Build `--values-json` in that shape, as in the upsert example above.

## Auth
- Provider id: `attio` (credential is collected as `custom.attio`)
- Collection: Bearer API key via the secure credential flow (`credentials.request_api_access`); created in Attio under Workspace settings > Developers
- Allowed hosts: `api.attio.com`
- Status check: `bin/attio.py auth` (must return `"ok": true`)

## Operating Rules
1. `upsert`, `note`, and `task` are writes: confirm which record is being touched and exactly what will be written, unless standing permission exists.
2. Reading (objects, query) needs no confirmation.
3. Attio applies standard API rate limits; back off on 429s and retry once after a short wait.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/attio.py

## Maturity
🧪 Draft: written from Attio's public API docs; not yet live-tested end-to-end.
