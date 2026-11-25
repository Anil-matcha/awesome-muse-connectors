---
name: "looot"
description: "Find and run business data lookups through looot: work emails, phone numbers, company and people search, Google results, web pages, news, LinkedIn profiles. One token, prepaid balance, price shown before each run. Trigger phrases: looot, find work email, find phone number, enrich company, search companies, search people."
metadata: { "includeInPrompt": true }
tagline: "Search a catalog of 2,500+ data API endpoints, see the price, and run them from one prepaid balance."
catalog_auth: "API token (per-user, prepaid balance)"
catalog_hosts: ["api.looot.ai"]
---

# looot

## Purpose
[looot](https://looot.ai) gives an agent one token and one prepaid balance for data API endpoints from many providers. This connector searches the catalog by task, shows an operation's price and inputs, runs it, and reads the balance. Use it when the user wants a work email, a phone number, company or people search, Google results, a web page's text, news, a LinkedIn profile, or local business data and does not name a specific provider.

Source: the public OpenAPI spec at https://api.looot.ai/openapi.json and the open-source n8n node at https://github.com/loootai/n8n-nodes-looot, both checked on 2026-10-08. Docs: https://docs.looot.ai.

## Tooling
All commands go through `bin/looot.py`. Each prints the API's JSON response.

```bash
bin/looot.py auth                                   # GET /v1/balance; prints {"ok": true, ...} on 200
bin/looot.py balance                                # GET /v1/balance
bin/looot.py search "find work email" --limit 10    # GET /v1/catalog/search?q=&limit=
bin/looot.py inspect serper-search                  # GET /v1/operations/{id}: price and input schema
bin/looot.py run serper-search --input '{"q": "looot data api"}'   # POST /v1/runs?wait=30, then polls GET /v1/runs/{runId}
bin/looot.py status <runId>                         # GET /v1/runs/{runId}
```

`run` sends a fresh random `idempotencyKey` per call, polls until the run is `completed`, `failed`, `blocked` or `stopped` or until `--timeout` seconds (default 120) pass, and prints `runId`, `status`, `result`, `actualCost` and `error`. If the deadline passes first it prints the `runId` so `status` can pick it up.

## Auth
- Provider id: `looot` (credential is collected as `custom.looot`)
- Collection: API token via the secure credential flow (`credentials.request_api_access`); the user creates it in the looot dashboard at https://looot.ai. Outside Muse, the CLI reads the token from the `LOOOT_TOKEN` environment variable. It never accepts a token as an argument.
- Connect placement: `Authorization: Bearer <token>`
- Required scopes: none; the token is tied to one workspace and its balance
- Allowed hosts: `api.looot.ai` (HTTPS only; redirects to any other host are refused)
- Status check: `bin/looot.py auth` (must return `"ok": true`). It calls `GET https://api.looot.ai/v1/balance`, which is free.

## Operating Rules
1. `auth`, `balance`, `search`, `inspect` and `status` are free reads and need no confirmation.
2. `run` spends prepaid balance. Always `inspect` the operation first, tell the user the price (`estimatedMaxCost`) and the inputs you will send, and get a yes before the run. Do not run a batch without the user approving the count and the total.
3. A failed run is not charged. A miss (no result found) is a normal answer, not an error; do not retry it in a loop.
4. If the balance is too low, report it and stop. Do not try to top up on the user's behalf.
5. Check the run's own `status` and `error`, not only the HTTP status: a run can return HTTP 201 with `status: "failed"`.
6. Never print, log, or transmit the token value.

## Files
- SKILL.md
- bin/looot.py

## Maturity
🧪 Draft: not live-tested with a token. Written from the public OpenAPI spec and the n8n node. `bin/looot.py` was compiled, its `--help` checked, and `auth` was checked against api.looot.ai with no token (clean local error) and with an invalid token (HTTP 401 surfaced). Authenticated calls, `run`, and the Muse credential flow have not been tested end-to-end.
