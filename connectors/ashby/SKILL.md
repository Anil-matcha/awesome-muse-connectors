---
name: "ashby"
description: "Search Ashby public job boards (no key needed) and read/write the Ashby ATS: candidates, jobs, applications. Trigger phrases: ashby, job board, candidates, hiring, job search."
metadata: { "includeInPrompt": true }
tagline: "Search Ashby public job boards (no key needed) and read/write the Ashby ATS: candidates, jobs, applications."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.ashbyhq.com"]
---

# Ashby

## Purpose
Two modes in one connector. (1) Credential-free public job search: list any Ashby-powered company's public job board with no API key. (2) Authenticated ATS for hiring teams: list candidates, jobs, and applications; create applications and move them through the pipeline. Most users will only need the public feed.

## Tooling
All commands go through `bin/ashby.py`:

```bash
bin/ashby.py jobs-public --org acme                        # public job board (no credential needed)
bin/ashby.py auth                                          # verify the ATS API key
bin/ashby.py candidate-list --json '{}'                    # list candidates
bin/ashby.py job-list --json '{}'                          # list jobs
bin/ashby.py application-list --json '{}'                  # list applications/pipeline
bin/ashby.py application-create --json '{...}'             # create an application (confirm first)
bin/ashby.py application-move --application-id A --stage-id S --json '{...}'  # move stages (confirm first)
```

Keyed endpoints are RPC-style POSTs; pass the request body with `--json` (field names follow the provider docs at developers.ashbyhq.com).

## Auth
- Provider id: `ashby` (credential is collected as `custom.ashby`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in Ashby under Admin > API Keys. The exact scheme is HTTP Basic with the key as the username and a blank password (`Authorization: Basic base64("<key>:")`). New keys have NO permissions by default: grant the module scopes for the endpoints you use, or calls fail.
- Public job feed: `GET https://api.ashbyhq.com/posting-api/job-board/{organizationHost}` needs NO credential. The CLI skips the credential load entirely for `jobs-public`, so that command works without any key on file.
- Allowed hosts: `api.ashbyhq.com`
- Status check: `bin/ashby.py auth` (must return `"ok": true`)

## Operating Rules
1. `jobs-public` is credential-free and needs no confirmation; it is the right tool for job searching.
2. `application-create`, `application-move`, and any pipeline move or rejection change a real hiring pipeline: confirm the candidate, stage, and job with the user before running, unless standing permission exists.
3. Reading (candidate-list, job-list, application-list) needs no confirmation.
4. Money-handling is read-only by default; every money-moving write is confirmation-gated, never automatic. Pipeline moves are people-affecting writes and get the same treatment.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/ashby.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/ashby.py

## Maturity
🧪 Draft: written from Ashby's public API docs; not yet live-tested end-to-end.
