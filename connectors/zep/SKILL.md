---
name: "zep"
description: "Work with Zep's temporal memory: create users and threads, append messages, read distilled facts and history. Trigger phrases: zep, knowledge graph memory, conversation memory."
metadata: { "includeInPrompt": true }
tagline: "Work with Zep's temporal memory: create users and threads, append messages, read distilled facts and history."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.getzep.com"]
---

# Zep

## Purpose
Use Zep as temporal knowledge-graph memory: create user containers and threads, append conversation messages (Zep extracts facts and entities asynchronously), read the distilled facts for a thread, and read message history. Use when the user mentions Zep or wants long-term conversation memory with fact extraction.

## Tooling
All commands go through `bin/zep.py` (pinned to API v2 threads):

```bash
bin/zep.py auth                                          # verify the API key
bin/zep.py user-create --user-id michael --email "m@example.com"   # create a user container
bin/zep.py thread-create --thread-id proj-alpha --user-id michael  # create a thread
bin/zep.py message-add --thread-id proj-alpha --role user --content "We decided to launch in October"  # append a message
bin/zep.py context --thread-id proj-alpha                  # distilled facts for the thread
bin/zep.py messages --thread-id proj-alpha --limit 20      # conversation history
```

## Auth
- Provider id: `zep` (credential is collected as `custom.zep`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created at app.getzep.com under Settings > API Keys
- Scheme: nonstandard `Authorization: Api-Key <key>` (exact: capital A, hyphen; NOT Bearer), sent verbatim by `bin/zep.py`
- Allowed hosts: `api.getzep.com`
- Status check: `bin/zep.py auth` (live check with `--thread-id`; without it, verifies the credential resolves)

## Operating Rules
1. `user-create`, `thread-create`, and `message-add` are writes: confirm with the user before running them, unless standing permission exists. Reads (context, messages) need no confirmation.
2. Fact extraction is async: after `message-add`, allow a few minutes before `context` reflects the new message. Do not claim facts are stored until `context` shows them.
3. Zep is metered on ingestion credits (1 credit per ~350 bytes of episode text; retrieval and storage are unmetered). Free tier is about 10k credits/month; paid plans start near $49/mo. Warn before bulk ingestion.
4. This connector is pinned to API v2 (threads); Zep is mid-migration from sessions to threads, so field names follow v2.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/zep.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/zep.py

## Maturity
🧪 Draft: written from Zep's public API docs; not yet live-tested end-to-end.
