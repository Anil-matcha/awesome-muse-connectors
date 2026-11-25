---
name: "railway"
description: "Read and write Railway: list projects and deployments, set environment variables, redeploy. Trigger phrases: railway, deploy."
metadata: { "includeInPrompt": true }
tagline: "List projects and deployments, set variables, redeploy."
catalog_auth: "API token (account or workspace)"
catalog_hosts: ["backboard.railway.com"]
---

# Railway

## Purpose
Read and write the user's Railway infrastructure through the Railway GraphQL API: list projects, inspect a project, list deployments, set environment variables, and redeploy deployments. Use when the user mentions Railway or deployments they host there.

## Tooling
All commands go through `bin/railway.py`:

```bash
bin/railway.py auth                                      # verify the token
bin/railway.py projects                                  # list projects (id, name)
bin/railway.py project --id proj_abc123                  # inspect one project
bin/railway.py deployments --project-id proj_abc123      # list deployments for a project
bin/railway.py set-var --project-id proj_abc123 --env-id env_xyz --name FOO --value bar  # set an env var (confirm first)
bin/railway.py redeploy --deployment-id dep_abc123       # redeploy a deployment (confirm first)
```

Every operation is a POST to the single GraphQL endpoint with `{"query": ..., "variables": {...}}`. Queries are kept minimal; `project` and `deployments` accept the IDs Railway returns from `projects`.

## Auth
- Provider id: `railway` (credential is collected as `custom.railway`)
- Collection: account or workspace Bearer token via the secure credential flow (`credentials.request_api_access`); created in the Railway dashboard under Tokens. Note: project tokens are a different mechanism (they use a `Project-Access-Token` header instead of `Authorization: Bearer`) and are out of scope for this CLI.
- Allowed hosts: `backboard.railway.com`
- Status check: `bin/railway.py auth` (must return `"ok": true`)

## Operating Rules
1. `set-var` and `redeploy` are writes: confirm the project, environment, variable name, and value with the user before running, unless standing permission exists.
2. Reading (projects, deployments) needs no confirmation.
3. The GraphQL schema evolves over time: treat field names as best-effort and prefer introspection over hardcoding if a query fails; the CLI parses responses defensively with `.get`.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/railway.py

## Maturity
🧪 Draft: written from Railway's public API docs; not yet live-tested end-to-end.
