---
name: "clickup"
description: "List ClickUp workspaces and tasks, and create tasks. Trigger phrases: clickup, clickup tasks, my clickup list."
metadata: { "includeInPrompt": true }
tagline: "List ClickUp workspaces and tasks, and create tasks."
catalog_auth: "ClickUp personal API token (per-user, Settings \u2192 Apps \u2192 API Token)"
catalog_hosts: ["api.clickup.com"]
---

# ClickUp

## Purpose
Work the user's ClickUp: list workspaces ("teams") (`teams`), list tasks in a list (`tasks`), and create tasks (`create`). ClickUp's API calls workspaces "teams": `teams` returns workspaces.

## Tooling
All commands go through `bin/clickup.py`:

```bash
bin/clickup.py teams                    # workspaces (id, name)
bin/clickup.py tasks --list 123456789   # tasks in a list (name, status, due date)
bin/clickup.py create --list 123456789 --name "Ship the thing"   # create a task
```

List ids come from ClickUp (open a list → the URL contains its numeric id). Use `teams` → space → folder → list navigation in ClickUp's UI to find the right list.

## Auth
- Provider id: `clickup` (credential is collected as `custom.clickup`)
- Collection: personal API token via the secure credential flow (`credentials.request_api_access`): create one in ClickUp → avatar → Settings → Apps → API Token (tokens start with `pk_`)
- Connect placement: `custom_header:Authorization` (ClickUp takes the **raw** token in the `Authorization` header: no `Bearer` prefix)
- Allowed hosts: `api.clickup.com`
- Status check: `bin/clickup.py teams` (a successful list proves the token works)

## Operating Rules
1. `create` is a write: confirm the task name and destination list with the user before running, unless standing permission exists.
2. Reading (`teams`, `tasks`) needs no confirmation.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/clickup.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/clickup.py

## Maturity
🧪 Draft: written from ClickUp's public API v2 docs; not yet live-tested end-to-end.
