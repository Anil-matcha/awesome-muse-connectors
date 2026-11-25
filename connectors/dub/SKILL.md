---
name: "dub"
description: "Read and write Dub: manage short links and read their click analytics; record lead or sale conversions. Trigger phrases: dub, short links."
metadata: { "includeInPrompt": true }
tagline: "Create short links, read analytics, track conversions."
catalog_auth: "API key (per-workspace)"
catalog_hosts: ["api.dub.co"]
---

# Dub

## Purpose
Manage Dub short links: list links, create new ones, update or delete them, read click analytics, and record lead or sale conversions against a click. Use when the user mentions Dub or short links.

## Tooling
All commands go through `bin/dub.py`:

```bash
bin/dub.py auth                                                  # verify the API key
bin/dub.py links --limit 25                                      # list links
bin/dub.py create --url "https://example.com/long" --key "launch"  # new short link
bin/dub.py update --id "clvabc123" --url "https://example.com/new"  # edit a link
bin/dub.py delete --id "clvabc123"                               # delete a link
bin/dub.py analytics --link-id "clvabc123"                       # click analytics
bin/dub.py track-lead --click-id "abc123"                        # record a lead
bin/dub.py track-sale --click-id "abc123" --amount 4900          # record a sale
```

Dub paths are unversioned: the base is `https://api.dub.co` with no `/v2`. The link id for `update` and `delete` is the `id` field from `links`. `--amount` on `track-sale` is in cents.

## Auth
- Provider id: `dub` (credential is collected as `custom.dub`)
- Collection: API key (`dub_...`) via the secure credential flow (`credentials.request_api_access`); created in the Dub dashboard under API keys
- Allowed hosts: `api.dub.co`
- Status check: `bin/dub.py auth` (must return `"ok": true`)

## Operating Rules
1. `create`, `update`, `delete`, `track-lead`, and `track-sale` are writes: confirm with the user first, unless standing permission exists. Deleting a link breaks its short URL.
2. Dub keys are per workspace; a key from one workspace cannot touch another.
3. On HTTP 429, back off and honor the `Retry-After` header before retrying.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/dub.py

## Maturity
🧪 Draft: written from Dub's public API docs; not yet live-tested end-to-end.
