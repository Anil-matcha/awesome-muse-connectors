---
name: "triggerdev"
description: "Read and write trigger.dev: list runs, check run status, trigger tasks, cancel runs, list schedules. Trigger phrases: trigger.dev, background jobs."
metadata: { "includeInPrompt": true }
tagline: "Trigger background jobs, list runs, manage schedules."
catalog_auth: "API key (per-environment)"
catalog_hosts: ["api.trigger.dev"]
---

# trigger.dev

## Purpose
Manage the user's trigger.dev background jobs: list runs, check a run's status and output, trigger task runs, cancel runs, and list schedules. Use when the user mentions trigger.dev or background jobs.

## Tooling
All commands go through `bin/triggerdev.py`:

```bash
bin/triggerdev.py auth                                     # verify the API key
bin/triggerdev.py runs --limit 25                          # list recent runs
bin/triggerdev.py run --id run_abc123                      # show one run's status and output
bin/triggerdev.py trigger --task my-task --payload-json '{"x":1}'  # trigger a task run
bin/triggerdev.py trigger --task my-task --payload-json '{}' --project-ref proj_abc123  # with a personal access token
bin/triggerdev.py cancel --run-id run_abc123               # cancel a run
bin/triggerdev.py schedules                                # list schedules
```

## Auth
- Provider id: `triggerdev` (credential is collected as `custom.triggerdev`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in the trigger.dev dashboard under API keys, sent in the standard Authorization header.
- Allowed hosts: `api.trigger.dev`
- Status check: `bin/triggerdev.py auth` (must return `"ok": true`)

## Operating Rules
1. `trigger` and `cancel` are writes: confirm the task, payload, or run ID with the user before running, unless standing permission exists. Triggering a task starts real compute that can cost money.
2. Reading (runs, run, schedules) needs no confirmation.
3. Runs are async: after `trigger`, poll `run --id` to watch the status move to COMPLETED or FAILED.
4. Personal access tokens need a project reference: pass `--project-ref` with `trigger` when the stored credential is a personal access token rather than a project API key.
5. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/triggerdev.py

## Maturity
🧪 Draft: written from trigger.dev's public API docs; not yet live-tested end-to-end.
