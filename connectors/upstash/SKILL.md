---
name: "upstash"
description: "Read and write Upstash: get, set, and delete Redis keys, run command pipelines. Trigger phrases: upstash, redis."
metadata: { "includeInPrompt": true }
tagline: "Run Redis commands over REST."
catalog_auth: "Per-database token (host declared at connect time)"
catalog_hosts: ["*.upstash.io"]
---

# Upstash

## Purpose
Work with an Upstash Redis database over its REST API: read keys, write keys with optional TTL, delete keys, and run batched command pipelines. Use when the user points at a specific Upstash database host.

## Tooling
Every command needs `--db-host` (the per-database host, https assumed; must end with `.upstash.io`):

```bash
bin/upstash.py --db-host mydb.upstash.io auth                                    # verify the token
bin/upstash.py --db-host mydb.upstash.io get --key "session:123"                 # read a key
bin/upstash.py --db-host mydb.upstash.io set --key "session:123" --value "abc"   # write a key
bin/upstash.py --db-host mydb.upstash.io set --key "otp:7" --value "4921" --ex 300  # write with 5-minute TTL
bin/upstash.py --db-host mydb.upstash.io delete --key "session:123"              # delete a key
bin/upstash.py --db-host mydb.upstash.io pipeline --commands-json '[["GET","a"],["SET","b","1"]]'  # batch commands
```

## Auth
- Provider id: `upstash` (credential is collected as `custom.upstash`)
- Collection: REST token via the secure credential flow (`credentials.request_api_access`); each database has its own token and host. The user declares their database host (`<database-id>.upstash.io`) at connect time.
- Allowed hosts: built at runtime from `--db-host`; the surrogate is only swapped for that host
- Status check: `bin/upstash.py --db-host <host> auth` (must return `"ok": true`)

## Operating Rules
1. One credential covers one database product: reads and writes need `--db-host` so the request goes to the right database.
2. Writes (set, delete, pipeline) need confirmation with the user first, unless standing permission exists. Reads (get) need none.
3. Blocking commands such as BLPOP are unsupported over the REST API; do not attempt them.
4. The separate Upstash Developer API (account management) is out of scope for v1.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/upstash.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/upstash.py

## Maturity
🧪 Draft: written from Upstash's public API docs; not yet live-tested end-to-end.
