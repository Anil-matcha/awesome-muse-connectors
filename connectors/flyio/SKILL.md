---
name: "flyio"
description: "Read and write Fly.io: list apps and machines, manage volumes, start/stop/restart machines, run exec commands. Trigger phrases: fly.io, machines."
metadata: { "includeInPrompt": true }
tagline: "List apps and machines, manage machine lifecycle."
catalog_auth: "API token (app or org scoped)"
catalog_hosts: ["api.machines.dev"]
---

# Fly.io

## Purpose
Read and write the user's Fly.io Machines through the Fly.io Machines REST API: list apps and machines, inspect machines and volumes, create machines, stop/start/restart them, and run one-off commands inside a machine with exec. Use when the user mentions Fly.io, fly apps, or their machines.

## Tooling
All commands go through `bin/flyio.py`:

```bash
bin/flyio.py auth                                            # verify the API key
bin/flyio.py apps --org personal                             # list apps in an org
bin/flyio.py machines --app myapp                            # list machines in an app
bin/flyio.py volumes --app myapp                             # list volumes in an app
bin/flyio.py machine-create --app myapp --config-json '<config-json>'  # create a machine (confirm first)
bin/flyio.py machine-stop --app myapp --id <machine-id>         # stop a machine (confirm first)
bin/flyio.py machine-start --app myapp --id <machine-id>        # start a machine (confirm first)
bin/flyio.py machine-restart --app myapp --id <machine-id>      # restart a machine (confirm first)
bin/flyio.py exec --app myapp --id <machine-id> --command "df -h"  # run a command in a machine (confirm first)
```

`--org` defaults to `personal` and is only used for `apps`. Machine IDs come from `machines`. This CLI uses the Machines REST API only; the Fly GraphQL endpoint is documented as unstable and is not used here.

## Auth
- Provider id: `flyio` (credential is collected as `custom.flyio`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); create one with `flyctl auth token` or in the Fly.io dashboard under Account > Tokens
- Allowed hosts: `api.machines.dev`
- Status check: `bin/flyio.py auth` (must return `"ok": true`)

## Operating Rules
1. `machine-create`, `machine-stop`, `machine-start`, and `machine-restart` are writes: confirm the exact action on the exact machine with the user before running, unless standing permission exists. Machine creation also incurs Fly.io usage costs.
2. `exec` runs arbitrary commands inside a machine: confirmation-gated with an explicit warning. Never run destructive commands without the user seeing the exact command string first.
3. Reading (apps, machines, volumes) needs no confirmation.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/flyio.py

## Maturity
🧪 Draft: written from Fly.io's public API docs; not yet live-tested end-to-end.
