---
name: "todoist"
description: "List tasks, create tasks, and complete them in Todoist. Trigger phrases: todoist, my tasks, add a task, todo list."
metadata: { "includeInPrompt": true }
tagline: "List tasks, create tasks, and mark them done in Todoist."
catalog_auth: "Todoist API token (per-user, Settings \u2192 Integrations \u2192 Developer)"
catalog_hosts: ["api.todoist.com"]
---

# Todoist

## Purpose
Work the user's Todoist: list tasks (`tasks`: content, due date, priority, project), create tasks (`create`), and mark tasks done (`complete`).

## Tooling
All commands go through `bin/todoist.py`:

```bash
bin/todoist.py tasks                                  # list tasks (content, due date, priority, project)
bin/todoist.py create --content "Water the plants"    # create a task
bin/todoist.py complete --id 1234567890               # mark a task done
```

Task ids come from `tasks` output.

## Auth
- Provider id: `todoist` (credential is collected as `custom.todoist`)
- Collection: API token via the secure credential flow (`credentials.request_api_access`): find it in Todoist → Settings → Integrations → Developer
- Connect placement: `bearer_header`
- Allowed hosts: `api.todoist.com`
- Status check: `bin/todoist.py tasks` (a successful list proves the token works)

## Operating Rules
1. `create` and `complete` are writes: confirm the task content/id with the user before running, unless standing permission to manage the list exists.
2. Reading (`tasks`) needs no confirmation.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/todoist.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/todoist.py

## Maturity
🧪 Draft: written from Todoist's public REST API v1 docs; not yet live-tested end-to-end.
