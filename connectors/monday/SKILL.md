---
name: "monday"
description: "Read and write monday.com: list boards, read items, create items. Trigger phrases: monday, monday.com board."
metadata: { "includeInPrompt": true }
tagline: "List boards, read items, create items. Project management over GraphQL."
catalog_auth: "personal API token (per-user)"
catalog_hosts: ["api.monday.com"]
---

# Monday

## Purpose
Read and write the user's monday.com workspace: list boards, read items on a board, create items. Use when the user mentions monday.com or a Monday board.

## Tooling
All commands go through `bin/monday.py`:

```bash
bin/monday.py auth                                      # verify the token
bin/monday.py boards --limit 25                         # list boards
bin/monday.py items --board BOARD_ID --limit 25          # list items on a board
bin/monday.py create-item --board BOARD_ID --name "Task"  # create an item
```

monday.com's API is GraphQL over a single endpoint; board arguments take board IDs. Use `boards` to resolve names first.

## Auth
- Provider id: `monday` (credential is collected as `custom.monday`)
- Collection: personal API token via the secure credential flow (`credentials.request_api_access`); created in monday.com under Administration > Connections > Personal API token (or avatar > Developers)
- Allowed hosts: `api.monday.com`
- Status check: `bin/monday.py auth` (must return `"ok": true`)

## Operating Rules
1. `create-item` is a write: confirm the board and item name with the user before creating, unless standing permission exists.
2. Reading (boards, items) needs no confirmation.
3. monday.com enforces a complexity budget per minute; keep limits modest and back off on `ComplexityException` errors.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/monday.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/monday.py

## Maturity
🧪 Draft: written from monday.com's public API docs; not yet live-tested end-to-end.
