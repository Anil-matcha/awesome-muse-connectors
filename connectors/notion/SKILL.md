---
name: "notion"
description: "Work with Notion: search pages, read page properties, query databases, create pages, append blocks, update page properties. Trigger phrases: notion, notion page, notion database."
metadata: { "includeInPrompt": true }
tagline: "Search and query Notion, plus create pages, append blocks, and update page properties (writes need --confirm)."
catalog_auth: "Notion internal integration token (per-user, created at notion.so/my-integrations)"
catalog_hosts: ["api.notion.com"]
---

# Notion

## Purpose
Work with the user's Notion workspace: search pages and databases, read page properties, query databases, and write: create pages, append blocks to a page, and update page properties. Use when the user mentions Notion or wants something looked up or recorded in their Notion.

## Tooling
All commands go through `bin/notion.py`:

```bash
bin/notion.py auth                              # verify the connection (search with page_size 1)
bin/notion.py search --query "roadmap"           # search pages and databases
bin/notion.py page --id PAGE_ID                  # read a page's properties
bin/notion.py query-db --id DATABASE_ID          # query a database (first 20 rows)

# writes: every one requires the exact --confirm string the CLI prints
bin/notion.py page-create --parent-id PAGE_ID --properties '{"title":{"title":[{"text":{"content":"My note"}}]}}'
bin/notion.py page-create --parent-id DB_ID --parent-type database --properties '{"Name":{"title":[{"text":{"content":"New row"}}]}}'
bin/notion.py block-append --block-id PAGE_ID --blocks '[{"object":"block","type":"paragraph","paragraph":{"rich_text":[{"type":"text","text":{"content":"Hello"}}]}}}]'
bin/notion.py page-update --id PAGE_ID --properties '{"Status":{"status":{"name":"Done"}}}'
```

IDs are the 32-hex-character Notion IDs (with or without dashes). `--properties` uses the Notion API property object format (e.g. `{"title": {"title": [...]}}`), not flattened values.

## Auth
- Provider id: `notion` (credential is collected as `custom.notion`)
- Collection: Notion internal integration token via the secure credential flow (`credentials.request_api_access`); create one at notion.so/my-integrations → New integration → copy the "Internal Integration Secret", then share the pages/databases you need with that integration inside Notion
- Required scopes: n/a (integration capabilities are set at notion.so/my-integrations)
- Allowed hosts: `api.notion.com`
- Status check: `bin/notion.py auth` (must return `"ok": true`)

## Operating Rules
1. Reads need no confirmation. Every write (`page-create`, `block-append`, `page-update`) requires the exact-match `--confirm` string: run the command once without it, read the refused string from the output, confirm the effect with the user, then re-run with it.
2. Notion rate-limits to ~3 requests/second; if a call returns 429, wait the `Retry-After` seconds and continue.
3. Pages and databases must be explicitly shared with the integration inside Notion, or they will not appear in search results and writes to them will fail: if a known page is missing, tell the user to share it with the integration.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/notion.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/notion.py

## Maturity
🧪 Draft: written from Notion's public API docs; not yet live-tested end-to-end. The write endpoints (`page-create`, `block-append`, `page-update`) are doc-built only: paths and bodies follow the public docs but have never been run against a real workspace.
