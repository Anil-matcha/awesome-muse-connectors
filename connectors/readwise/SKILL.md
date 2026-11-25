---
name: "readwise"
description: "Read and write Readwise: list books and highlights, save new highlights. Trigger phrases: readwise, my highlights, reading list."
metadata: { "includeInPrompt": true }
tagline: "Search your highlights and books, save new highlights."
catalog_auth: "access token (per-user, from readwise.io/access_token)"
catalog_hosts: ["readwise.io"]
---

# Readwise

## Purpose
Read and write the user's Readwise library: list books, list highlights, save new highlights. Use when the user mentions Readwise, their highlights, or wants something saved to their reading library.

## Tooling
All commands go through `bin/readwise.py`:

```bash
bin/readwise.py auth                                    # verify the token
bin/readwise.py books --limit 20                        # list books in the library
bin/readwise.py highlights --limit 20                   # list highlights
bin/readwise.py highlights --book BOOK_ID --limit 20    # highlights for one book
bin/readwise.py add --text "quote" --title "Title" --author "Author"  # save a highlight
```

## Auth
- Provider id: `readwise` (credential is collected as `custom.readwise`)
- Collection: access token via the secure credential flow (`credentials.request_api_access`); created at readwise.io/access_token
- Allowed hosts: `readwise.io`
- Status check: `bin/readwise.py auth` (must return `"ok": true`)

## Operating Rules
1. `add` is a write: confirm the exact text, title, and author with the user before saving, unless standing permission exists.
2. Reading (books, highlights) needs no confirmation.
3. Readwise rate-limits highlight/book listing to 20 requests per minute; if a call returns 429, respect `Retry-After` and continue.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/readwise.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/readwise.py

## Maturity
🧪 Draft: written from Readwise's public API docs; not yet live-tested end-to-end.
