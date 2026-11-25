---
name: "descript"
description: "Work with Descript projects and async Underlord/agent jobs: list projects, submit publish jobs, poll job status. Trigger phrases: descript, video editing, publish video, descript project."
metadata: { "includeInPrompt": true }
tagline: "Work with Descript's API (open beta): list projects, inspect Underlord/agent jobs, submit a publish job, and poll a job until it finishes. Use when the user wants to drive Descript editing or publishing programmatically."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.descript.com"]
---

# Descript

## Purpose
Work with Descript's API (open beta): list projects, inspect Underlord/agent jobs, submit a publish job, and poll a job until it finishes. Use when the user wants to drive Descript editing or publishing programmatically.

## Tooling
All commands go through `bin/descript.py`:

```bash
bin/descript.py auth                                   # verify the API key
bin/descript.py projects                               # list projects
bin/descript.py project --id PROJECT_ID                # get one project
bin/descript.py jobs                                   # list Underlord/agent jobs
bin/descript.py job-status --id JOB_ID                 # get job status once
bin/descript.py job-status --id JOB_ID --wait          # poll until job_state is "stopped"
bin/descript.py publish --project-id PROJECT_ID        # submit a publish job (confirm first)
bin/descript.py job-delete --id JOB_ID                 # delete a job (confirm first)
```

Jobs are async: submit with `publish`, then poll with `job-status --wait` until `job_state` is `stopped`, then check `status` for success/partial/error. The publish body schema follows Descript's API docs; pass `--body` as raw JSON if the default empty body is not enough for your case.

Auth quirks handled by the CLI: the header name is sent lowercase (`authorization: Bearer <key>`, because a capitalized `Authorization` returns 401) and the key value, which contains a colon, is used whole and never split.

## Auth
- Provider id: `descript` (credential is collected as `custom.descript`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); create one in your Descript account's API settings
- Header: `authorization: Bearer <key>` verbatim, lowercase header name (the CLI sets it exactly)
- Allowed hosts: `api.descript.com`
- Status check: `bin/descript.py auth` (lists projects; a successful list proves the key works)

## Operating Rules
1. **Confirm before `publish`**: publishing sends content live. Name the project and get explicit approval.
2. **Confirm before `job-delete`**: name the job id.
3. Descript usage is credit-based; every publish job burns credits. Say so when confirming.
4. Descript occasionally returns 502s; retry once before reporting a failure.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/descript.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/descript.py

## Maturity
Draft: written from Descript's public API docs; not yet live-tested end-to-end. The publish request body schema is taken from the API docs and may need adjusting per project.
