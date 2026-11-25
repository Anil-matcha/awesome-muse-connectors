---
name: "ticktick"
description: "Read and write TickTick: list projects and tasks, create tasks, complete and delete tasks. Trigger phrases: ticktick, task list, my tasks."
metadata: { "includeInPrompt": true }
tagline: "Read and write TickTick: list projects and tasks, create tasks, complete and delete tasks."
catalog_auth: "OAuth 2.0 via the secure credential flow"
catalog_hosts: ["api.ticktick.com"]
---

# TickTick

## Purpose
Read and write the user's TickTick task lists: list projects (task lists), read a project's tasks, create tasks, mark tasks complete, delete tasks. Use when the user mentions TickTick or their tasks there.

## Tooling
All commands go through `bin/ticktick.py`:

```bash
bin/ticktick.py auth                                     # verify the OAuth token
bin/ticktick.py projects                                 # list task lists
bin/ticktick.py project-data --project-id abc123        # tasks in one list
bin/ticktick.py task-create --title "Call bank" --project-id abc123 --due-date 2026-09-17T09:00:00+0000
bin/ticktick.py task-complete --project-id abc123 --task-id xyz789
bin/ticktick.py task-delete --project-id abc123 --task-id xyz789
```

Use `projects` first to resolve a project ID. `due-date` accepts TickTick's format, e.g. `2026-09-17T09:00:00+0000`. Priority runs 0 (none) to 5 (highest).

## Auth
- Provider id: `ticktick` (credential is collected as `custom.ticktick`)
- Collection: OAuth 2.0 via the secure credential flow (`credentials.request_api_access`); register an app at developer.ticktick.com (free self-serve), authorize with scopes `tasks:read` and `tasks:write`
- Allowed hosts: `api.ticktick.com`
- Status check: `bin/ticktick.py auth` (must return `"ok": true`)
- Tokens last roughly 180 days; when `auth` starts failing with 401, reconnect to mint a fresh token.

## Operating Rules
1. `task-delete` is destructive: confirm the exact task with the user before deleting, unless standing permission exists.
2. `task-create` is a write: confirm the title and list (or note it needs one) before creating, unless standing permission exists.
3. `task-complete` is low-risk and reversible: no confirmation needed beyond the user's request.
4. This API covers tasks and projects only. Do not promise habits, notes, or calendar endpoints; they do not exist in TickTick's Open API.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/ticktick.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/ticktick.py

## Maturity
🧪 Draft: written from TickTick's public Open API docs; not yet live-tested end-to-end.
