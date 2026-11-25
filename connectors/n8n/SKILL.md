---
name: "n8n"
description: "Read and write n8n: list workflows, inspect and update them, list executions. Trigger phrases: n8n, workflows."
metadata: { "includeInPrompt": true }
tagline: "List and manage workflows, read executions."
catalog_auth: "API key (instance; host declared at connect time)"
catalog_hosts: ["your n8n instance host"]
---

# n8n

## Purpose
Read and write the user's n8n workflows through the n8n public REST API: list workflows, inspect a workflow, create and update workflows, and list executions. Use when the user mentions n8n or their automations.

## Tooling
All commands go through `bin/n8n.py`. Every command takes a required `--host`: your instance base URL, e.g. `https://myname.app.n8n.cloud` or `https://n8n.example.com` (self-hosted).

```bash
bin/n8n.py auth --host https://myname.app.n8n.cloud                    # verify the API key
bin/n8n.py workflows --host https://myname.app.n8n.cloud              # list workflows
bin/n8n.py workflow --host https://myname.app.n8n.cloud --id wf_abc   # inspect one workflow
bin/n8n.py create --host https://myname.app.n8n.cloud --name "Nightly sync" --nodes-json '[{"name":"Start",...}]'  # create a workflow
bin/n8n.py update --host https://myname.app.n8n.cloud --id wf_abc --workflow-json '{"name":"Nightly sync v2","nodes":[...]}'  # update a workflow (confirm first)
bin/n8n.py executions --host https://myname.app.n8n.cloud             # list executions
bin/n8n.py executions --host https://myname.app.n8n.cloud --workflow-id wf_abc  # executions for one workflow
```

Updates use the "GET first, strip, modify, PUT" pattern: PUT is a full replace, so the CLI fetches the current workflow, strips forbidden fields (`pinData`, `settings`), merges your changes, and then PUTs. Never PUT a partial object.

## Auth
- Provider id: `n8n` (credential is collected as `custom.n8n`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in n8n under Settings > n8n API. The key is sent in the `X-N8N-API-KEY` header.
- Allowed hosts: your n8n instance host, declared at connect time (the `--host` you pass; validated to start with `http://` or `https://`)
- Status check: `bin/n8n.py auth --host <your-host>` (must return `"ok": true`)

## Operating Rules
1. `update` is a destructive write: PUT replaces the whole workflow. Confirm the workflow ID and exactly what changes before running, unless standing permission exists. The CLI always GETs the current workflow first and strips forbidden fields (`pinData`, `settings`) before PUT.
2. There is no execute-by-ID endpoint in the n8n public API; running a workflow goes through its webhook trigger URL, which is separate from this CLI.
3. The public REST API is unavailable on n8n Cloud free trials (Starter plan or higher; self-hosted instances always work).
4. Reading (workflows, executions) needs no confirmation.
5. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/n8n.py

## Maturity
🧪 Draft: written from n8n's public API docs; not yet live-tested end-to-end.
