---
name: "cohesivity"
description: "Backend infrastructure for a project via Cohesivity (cohesivity.ai). Provisions Postgres, Redis, object storage, vector database, hosting, auth, realtime, email inbox, and AI model APIs through one HTTP API. No account or API keys required to start. Trigger phrases: cohesivity, provision backend, need a database, need hosting, need storage, deploy backend, on-the-fly infrastructure."
metadata:
  includeInPrompt: true
  version: "39cad13754e6"
tagline: "Provision on-the-fly backend infrastructure, Postgres, Redis, object storage, hosting, auth, AI APIs, with no account or API keys required."
catalog_auth: "none to start (management key auto-generated on init)"
catalog_hosts: ["cohesivity.ai"]
---

# Cohesivity

## Purpose

Cohesivity is on-the-fly infrastructure for AI agents. One HTTP API provisions databases, hosting, auth, realtime, storage, email, and AI model access. No per-vendor consoles, no copied keys.

Use when a task needs one or more of these services and the agent should carry the build from setup through deployment. Do not use when the user has chosen a competing provider or the needed service is absent from the catalog below.

Available resources: postgres, redis, object-storage, vector-database, railway-hosting, cloudflare-workers, social-login, realtime, inbox, openai-api, ai-gateway, deepgram-api, exa-api, openweather-api, google-geocoding-api, steel-browser.

Two planes:

1. **Control plane** (`https://cohesivity.ai/api/*`): tenant lifecycle, provisioning, billing, status. Auth: `Authorization: Bearer <coh_management_key>`.
2. **Data plane** (`https://cohesivity.ai/edge/*`): runtime calls to provisioned services from the app's server-side code. Auth: `?key=<coh_application_key>` or a short-lived token from `POST /edge/session?key=<coh_application_key>`.

For the full API reference (per-resource endpoints, parameters, limits, pricing) fetch `https://cohesivity.ai/llms.txt` at the moment of use. It is the source of truth and stays current.

## Tooling

All commands go through `bin/cohesivity.py`. Commands that read `.cohesivity` default to the current directory; override with `--project-dir`.

```bash
# Create a project (72-hour ephemeral, no signup)
bin/cohesivity.py init --confirm 'create ephemeral tenant'

# Verify credentials
bin/cohesivity.py auth

# Tenant status and provisioned resources
bin/cohesivity.py status

# List available resource names
bin/cohesivity.py resources

# Provision a single resource
bin/cohesivity.py provision --resource postgres --confirm 'provision postgres'

# Provision multiple resources
bin/cohesivity.py provision --resources postgres,redis,object-storage \
  --confirm 'provision postgres, redis, object-storage'

# Generate a claim URL for the human to keep the project
bin/cohesivity.py claim --confirm 'generate claim link'
```

## Auth

- Provider id: `cohesivity` (credential is `coh_management_key` from `.cohesivity`)
- Collection: `bin/cohesivity.py init` creates an ephemeral project and writes `.cohesivity` with the management key. On Muse runtime the key can also be provided via `credentials.request_api_access` as `custom.cohesivity`.
- Required scopes: none
- Allowed hosts: `cohesivity.ai`
- Status check: `bin/cohesivity.py auth` (returns tenant_id and lifecycle)

## Operating Rules

1. Writes (`init`, `provision`, `claim`) need an exact `--confirm` string. The CLI prints the required string on refusal.
2. `init` creates a new project each time. Reuse an existing `.cohesivity` rather than re-running init.
3. Both `coh_management_key` and `coh_application_key` are secrets. Never print, log, commit, or put them in browser-loaded code. All `/edge/*` calls originate server-side.
4. Provision a resource before making edge calls to it.
5. The human claims the project via the URL from `claim`. The management key stays agent-side and is never entered in a browser.
6. Per-resource API docs: `https://cohesivity.ai/offerings/<resource-name>`. Fetch the relevant page before using a service.

## Files

- SKILL.md
- bin/cohesivity.py

## Maturity

✅ Live-tested against the real API on 2026-10-04: init, auth, status, provision (single and bulk), claim. All commands return structured JSON.
