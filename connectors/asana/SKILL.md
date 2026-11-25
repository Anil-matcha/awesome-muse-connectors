---
name: "asana"
description: "Read and manage Asana tasks: my tasks, task details, create tasks. Trigger phrases: asana, my tasks, task list, todo."
metadata: { "includeInPrompt": true }
tagline: "View your assigned Asana tasks and create new ones."
catalog_auth: "Asana personal access token (per-user, My Settings \u2192 Apps \u2192 Manage Developer Apps)"
catalog_hosts: ["app.asana.com"]
---

# Asana

## Purpose
Work with the user's Asana: view tasks assigned to them and create new tasks. Use when the user mentions Asana, their tasks, or a todo list.

## Tooling
All commands go through `bin/asana.py`:

```bash
bin/asana.py me                                        # verify the connection, shows user gid
bin/asana.py tasks                                     # tasks assigned to me
bin/asana.py create --name "Ship v2" --notes "details"  # create a task
bin/asana.py create --name "Ship v2" --workspace-gid 1234567890123456 --notes "x"
```

`create` needs a workspace gid; pass `--workspace-gid` explicitly, or ask the user which workspace if unknown.

## Auth
- Provider id: `asana` (credential is collected as `custom.asana`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`): an Asana personal access token (My Settings → Apps → Manage Developer Apps), pasted once into the hosted form
- Allowed hosts: `app.asana.com`
- Status check: `bin/asana.py me` (must return the user's `gid` and `name`)

## Operating Rules
1. `create` is a write: confirm the task name (and workspace) with the user before creating, unless standing permission exists.
2. Reading (`me`, `tasks`) needs no confirmation.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/asana.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/asana.py

## Maturity
🧪 Draft: written from Asana's public REST API docs; not yet live-tested end-to-end.
