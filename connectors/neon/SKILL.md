---
name: "neon"
description: "Inspect Neon serverless Postgres: projects, branches, databases. Branch create and delete need exact-match confirmation; connection passwords are masked. Trigger phrases: neon, serverless postgres, database branch, postgres project."
metadata: { "includeInPrompt": true }
tagline: "Inspect Neon serverless Postgres projects, branches, and databases. Branch create and delete need exact-match confirmation; connection passwords are masked."
catalog_auth: "API key (per-user)"
catalog_hosts: ["console.neon.tech"]
---

# Neon

## Purpose
Manage Neon serverless Postgres infrastructure through the Neon Management API: list projects, inspect one project, list branches, create or delete a branch, and list databases. Reach for this when the user wants to inspect or provision database infrastructure. SQL queries run over the Postgres wire protocol, so this connector manages infrastructure only; it does not run queries.

## Tooling
All commands go through `bin/neon.py`:

```bash
bin/neon.py auth                                          # verify the API key
bin/neon.py projects                                      # list projects
bin/neon.py project-get --project-id PROJ_ID              # one project
bin/neon.py branches --project-id PROJ_ID                 # list branches
bin/neon.py branch-create --project-id PROJ_ID --name dev \
    --confirm "create branch dev in project PROJ_ID"       # create a branch (HIGH)
bin/neon.py branch-delete --project-id PROJ_ID --branch-id BR_ID \
    --confirm "delete branch BR_ID in project PROJ_ID"     # delete a branch (HIGH)
bin/neon.py databases --project-id PROJ_ID                # list databases
```

Branch create accepts an optional `--parent-branch-id` to branch from a non-default branch.

## Auth
- Provider id: `neon` (credential is collected as `custom.neon`)
- Collection: API key (Neon console > Account settings > API keys) via the secure credential flow (`credentials.request_api_access`)
- Auth scheme: `Authorization: Bearer <api key>` on every request
- Allowed hosts: `console.neon.tech`
- Status check: `bin/neon.py auth`

## Operating Rules
1. **Branch create and branch delete are HIGH actuations.** Creating a branch provisions a live database branch with compute that can incur billable usage; deleting one is irreversible and destroys the branch, its compute endpoint, and its data. Both require `--confirm` with the exact string the CLI echoes on every call. Missing or mismatched confirmation refuses the call.
2. **Connection strings are secrets.** The branch-create response includes connection URIs that embed database passwords. The CLI masks the password portion (`user:***@host`) on display. Never print, log, transmit, or paste a full connection string into chat. If a connection string is needed for app config, deliver it only to the exact destination the user named.
3. Reads (projects, branches, databases) need no confirmation. Surface choices before any write: name the project, the branch name, and the parent branch, and default cautiously. Never create a branch in a project the user did not choose.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/neon.py`). Do not print, log, or transmit the API key.
5. Honesty flags (unverified while building this connector): the task brief named `api.neon.tech`, but the verified Neon Management API host is `console.neon.tech`; the CLI uses the verified host. The branch DELETE path was not explicitly confirmed in the docs consulted; the CLI surfaces Neon's own error if it differs.

## Files
- SKILL.md
- bin/neon.py

## Maturity
Draft: written from Neon's public API docs; not yet live-tested end-to-end.
