---
name: "mem0"
description: "Mem0 memory CLI: add memories from messages, semantic search, read or delete memories, poll async events. Trigger phrases: mem0, memory layer, remember this."
metadata: { "includeInPrompt": true }
tagline: "Mem0 memory CLI: add memories from messages, semantic search, read or delete memories, poll async events."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.mem0.ai"]
---

# mem0

## Purpose
Manage the user's mem0 memory layer: store memories extracted from messages, run semantic search over them, and handle the full lifecycle (list, read, delete) scoped by user, agent, or app. Use when the user mentions mem0, a persistent memory layer, or asks to remember or recall facts.

## Tooling
All commands go through `bin/mem0.py`. Add and search are **async**: they return an `event_id`, which you poll with `status`.

```bash
bin/mem0.py auth                                                          # verify the API key
bin/mem0.py add --user-id alice --message "Michael prefers morning standups"  # store a memory (async)
bin/mem0.py status --event-id <event_id>                                  # poll an add/search event
bin/mem0.py search --user-id alice --query "meeting preferences"          # semantic search (async)
bin/mem0.py list --user-id alice                                          # list memories for a user
bin/mem0.py get --id <memory_id>                                          # get one memory
bin/mem0.py history --id <memory_id>                                      # change log of one memory
bin/mem0.py delete --id <memory_id>                                       # delete one memory (confirm first)
bin/mem0.py wipe --user-id alice                                          # delete ALL memories in scope (confirm first)
```

`add` needs one scope identifier (`--user-id`, `--agent-id`, `--app-id`, or `--run-id`); `--role` defaults to `user`.

## Auth
- Provider id: `mem0` (credential is collected as `custom.mem0`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created at app.mem0.ai (keys look like `m0-...`; agents can self-mint via `mem0 init --agent`)
- Scheme: nonstandard `Authorization: Token <key>` (NOT Bearer), plus `Accept: application/json`; sent verbatim by `bin/mem0.py`
- Allowed hosts: `api.mem0.ai`
- Status check: `bin/mem0.py auth` (must return `"ok": true`)

## Operating Rules
1. `add`, `delete`, and especially `wipe` are writes: confirm with the user before running them, unless standing permission exists. `wipe` deletes every memory in the scope; say exactly which scope it hits before confirming.
2. Reading (search, list, get, history, status) needs no confirmation.
3. Add and search are async: after `add` or `search`, poll `status --event-id <event_id>` until the event reports success, then read the results. Do not invent memory contents before the poll succeeds.
4. mem0 v3 add is add-only: it does not auto-update or auto-delete older conflicting memories, so check `search` first when a fact may already exist.
5. Free Hobby tier: 10k add requests + 1k retrieval requests per month. Stay inside it; warn before bulk operations.
6. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/mem0.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/mem0.py

## Maturity
🧪 Draft: written from mem0's public API docs; not yet live-tested end-to-end.
