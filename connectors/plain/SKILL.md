---
name: "plain"
description: "Read and write Plain support: find and upsert customers, list threads, create and reply to support threads. Trigger phrases: plain, support tickets."
metadata: { "includeInPrompt": true }
tagline: "Find customers, manage support threads."
catalog_auth: "Machine-user API key"
catalog_hosts: ["core-api.uk.plain.com"]
---

# Plain

## Purpose
Manage the user's Plain support inbox: find and upsert customers, list support threads, open new threads, and reply to threads. Use when the user mentions Plain or support tickets.

## Tooling
All commands go through `bin/plain.py`:

```bash
bin/plain.py auth                                     # verify the Machine User API key
bin/plain.py customer-find --email "them@example.com" # find a customer by email
bin/plain.py threads --limit 25                       # list threads (Relay cursor pagination, max 100 per page)
bin/plain.py customer-upsert --email "them@example.com" --name "Them"  # create or update a customer
bin/plain.py thread-create --customer-id c_abc123 --title "Bug report" --text "Details here"  # open a support thread
bin/plain.py thread-reply --thread-id t_abc123 --text "We are on it"  # reply to a thread
```

Plain's endpoint is UK-hosted (`core-api.uk.plain.com`); latency is normal for a cross-region call.

Schema reference: every operation is a minimal GraphQL query or mutation against Plain's published schema at `https://core-api.uk.plain.com/graphql/v1/schema.graphql`. Field selection in the CLI is conservative on purpose (`id` on node types, standard Relay `pageInfo`), and all parsing is defensive (`.get` with defaults), so a schema difference surfaces as a GraphQL error rather than a crash. If an operation errors on field names, check the schema URL above and adjust.

## Auth
- Provider id: `plain` (credential is collected as `custom.plain`)
- Collection: Machine User API key via the secure credential flow (`credentials.request_api_access`); created in Plain under Settings > Machine Users
- Allowed hosts: `core-api.uk.plain.com`
- Status check: `bin/plain.py auth` (must return `"ok": true`)

## Operating Rules
1. `customer-upsert`, `thread-create`, and `thread-reply` are writes: confirm the customer and thread involved, and show the exact message text, before running, unless standing permission exists.
2. Reading (customer-find, threads) needs no confirmation.
3. Plain paginates threads with Relay cursors (first/after, edges/node, max 100 per page): use `--limit` and follow `pageInfo.hasNextPage` for larger sweeps.
4. Plain applies API rate limits; back off on 429s.
5. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/plain.py

## Maturity
🧪 Draft: written from Plain's public API docs; not yet live-tested end-to-end.
