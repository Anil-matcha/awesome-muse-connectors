---
name: "coda"
description: "Read and write Coda: list docs, read tables and rows, add rows. Trigger phrases: coda, coda doc, coda table."
metadata: { "includeInPrompt": true }
tagline: "List docs, read tables and rows, add rows. Your docs as a database."
catalog_auth: "personal API token (per-user)"
catalog_hosts: ["coda.io"]
---

# Coda

## Purpose
Read and write the user's Coda workspace: list docs, list tables in a doc, read table rows, add rows to a table. Use when the user mentions Coda, a Coda doc, or a Coda table.

## Tooling
All commands go through `bin/coda.py`:

```bash
bin/coda.py auth                                        # verify the token (whoami)
bin/coda.py docs --limit 25                             # list docs
bin/coda.py tables --doc DOC_ID                         # list tables in a doc
bin/coda.py rows --doc DOC_ID --table TABLE_ID          # read rows from a table
bin/coda.py add-row --doc DOC_ID --table TABLE_ID --cells '{"Task":"Ship","Done":false}'  # add a row
```

Table arguments accept table IDs or names. Use `tables` to resolve names first.

## Auth
- Provider id: `coda` (credential is collected as `custom.coda`)
- Collection: personal API token via the secure credential flow (`credentials.request_api_access`); created at coda.io/account (API settings)
- Allowed hosts: `coda.io`
- Status check: `bin/coda.py auth` (must return `"ok": true`)

## Operating Rules
1. `add-row` is a write: confirm the exact cells and destination table with the user before sending, unless standing permission exists.
2. Reading (docs, tables, rows) needs no confirmation.
3. Coda API tokens can be read-only or read-write; if `add-row` returns a permission error, the token needs write scope: tell the user rather than retrying.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/coda.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/coda.py

## Maturity
🧪 Draft: written from Coda's public API docs; not yet live-tested end-to-end.
