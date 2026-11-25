---
name: "supermemory"
description: "Store and recall with Supermemory: add memories and documents, hybrid search, upload files, tune settings. Trigger phrases: supermemory, memory engine, remember this."
metadata: { "includeInPrompt": true }
tagline: "Store and recall with Supermemory: add memories and documents, hybrid search, upload files, tune settings."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.supermemory.ai"]
---

# Supermemory

## Purpose
Use Supermemory as the user's long-term memory and document store: add memories or documents (optionally isolated per user or project with `containerTag`), run hybrid semantic-plus-keyword search, list stored documents, upload files (PDFs, images, video, code), and tune extraction settings. Use when the user mentions Supermemory or wants to remember and recall across sessions.

## Tooling
All commands go through `bin/supermemory.py`:

```bash
bin/supermemory.py auth                                                   # verify the API key
bin/supermemory.py add --content "Michael ships on Fridays" --container-tag michael   # store a memory
bin/supermemory.py search --query "release schedule" --container-tag michael          # hybrid search
bin/supermemory.py list --container-tag michael --limit 25                 # list stored documents
bin/supermemory.py upload --file ./notes.pdf --container-tag michael      # upload a file
bin/supermemory.py settings --json '{"chunkSize": 512}'                   # tune extraction/chunking
```

`containerTag` isolates memory per user or project (max 100 chars); use one consistently for the user's personal memory.

## Auth
- Provider id: `supermemory` (credential is collected as `custom.supermemory`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); minted at console.supermemory.ai (keys start with `sm_`)
- Scheme: `Authorization: Bearer <key>` via surrogate placement
- Allowed hosts: `api.supermemory.ai`
- Status check: `bin/supermemory.py auth` (must return `"ok": true`)

## Operating Rules
1. `add`, `upload`, and `settings` are writes: confirm with the user before running them, unless standing permission exists. Say which `containerTag` the write targets.
2. Reading (search, list) needs no confirmation.
3. File uploads go to Supermemory's storage; confirm the file and its tag first. Large or sensitive files deserve a second look.
4. `settings` changes extraction behavior for everything stored later; confirm the exact JSON payload first.
5. Supermemory offers a generous free tier (paid plans from ~$16/mo). A self-hosted binary mirrors the same API at `http://localhost:6767`; this connector targets the cloud host unless a self-host variant is requested.
6. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/supermemory.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/supermemory.py

## Maturity
🧪 Draft: written from Supermemory's public API docs; not yet live-tested end-to-end.
