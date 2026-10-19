---
name: "cloudflare"
description: "Full Cloudflare API operations: token verification, accounts, zones, DNS, Pages deploys, Workers, KV, secrets, routes. Trigger phrases: cloudflare, dns record, pages deploy, worker, kv namespace."
metadata: { "includeInPrompt": true }
tagline: "Full Cloudflare operations: token verification (user and account-owned tokens), accounts, zones, DNS read/add, Pages project + direct-upload deploys, Workers deploy with KV bindings, Worker secrets and routes. Writes are confirmation-gated."
catalog_auth: "API token (per-user) via the secure credential flow"
catalog_hosts: ["api.cloudflare.com"]
---

# Cloudflare

## Purpose
Operate a Cloudflare account through the public API: verify the token (correctly, for both user and account-owned tokens), list accounts and zones, read and add DNS records, add zones, manage Pages projects and deploy sites by direct upload, create Workers KV namespaces, deploy Workers with KV bindings, upload Worker secrets, and add Worker routes. Use when the user mentions Cloudflare, DNS, a Pages site, or a Worker.

Source: Cloudflare API documentation (developers.cloudflare.com/api), checked 2026-10-19.

## Tooling
All commands go through `bin/cloudflare.py`. Output is JSON.

```bash
bin/cloudflare.py auth [--account-id <id>]        # status check: verify the token (see Auth)
bin/cloudflare.py accounts                        # list accounts the token can see
bin/cloudflare.py zones [--name example.com]      # list zones
bin/cloudflare.py dns-list <zone-name>            # read DNS records for a zone

# Writes — every one requires --confirm naming the exact effect:
bin/cloudflare.py zone-add <domain> --confirm "add zone example.com"
bin/cloudflare.py dns-add <zone> --type A --name www --content 192.0.2.1 [--ttl 3600] [--proxied] [--priority N] --confirm "add A record www -> 192.0.2.1"
bin/cloudflare.py pages-projects                  # list Pages projects
bin/cloudflare.py pages-project-create <name> --confirm "create Pages project mysite"
bin/cloudflare.py pages-deploy <project> --dir <dir> --confirm "deploy ./site to Pages project mysite"
bin/cloudflare.py workers-kv-create <title> --confirm "create KV namespace sessions"
bin/cloudflare.py workers-deploy <name> --file worker.js [--kv NAME:NAMESPACE_ID]... --confirm "deploy Worker api"
bin/cloudflare.py workers-secret-put <script> <KEY> --from-file <path> --confirm "set secret API_KEY on Worker api"
bin/cloudflare.py workers-route-add <zone> --pattern "example.com/api/*" --script <name> --confirm "route api/* to Worker api"
```

Account-scoped commands resolve the account from `GET /accounts`; pass `--account-id` when the token's scopes can't list accounts. `pages-deploy` needs the Python `blake3` package (`pip install blake3`) for Wrangler-compatible asset hashes.

## Auth
- Provider id: `cloudflare` (credential is collected as `custom.cloudflare`)
- Collection: API token via the secure credential flow (`credentials.request_api_access`). Create it under My Profile > API Tokens (or the account's API Tokens page for account-owned tokens) with only the scopes you need.
- Required scopes: reads need `Zone:Read` + `DNS:Read`; writes add the matching edit scopes — `DNS:Edit`, `Workers Scripts:Edit`, `Workers KV Storage:Edit`, Pages edit. Start read-only and widen deliberately.
- Allowed hosts: `api.cloudflare.com`
- Status check: `bin/cloudflare.py auth`

**Token types and verification (learned in production):** Cloudflare API tokens come in two ownership flavors with different prefixed formats — account-owned tokens start `cfat_`, user tokens start `cfut_`. Length alone is not a validity test. `/user/tokens/verify` returns 401 for account-owned tokens **by design**; verify those at `/accounts/<account-id>/tokens/verify` (that's what `auth --account-id` does) or with a capability probe. Also: R2 S3-compatible credentials (Access Key ID + Secret Access Key) are **not** REST API Bearer tokens and will 401 on every REST call — the fix is issuing a scoped REST API token, not re-pasting.

## Operating Rules
1. **Every write is confirmation-gated in code** — zone-add, dns-add, pages-project-create, pages-deploy, workers-kv-create, workers-deploy, workers-secret-put, and workers-route-add all refuse to run without `--confirm "<exact effect>"`. Get the user's confirmation in conversation first; never pre-fill it.
2. `pages-deploy` is a Direct Upload deploy and becomes the production deployment immediately. If the same Pages project is also connected to a Git repository, a push triggers its own deploy and supersedes the direct upload — keep the repo and the deployed directory in sync, or the next push reverts your deploy.
3. `_redirects` files are **not** honored on Direct Upload deploys (they deploy as static assets but Pages ignores them for routing). For short links, use static redirect pages (a small HTML file with meta-refresh + canonical link) instead.
4. Workers deploy as ES modules (`"type": "module"` metadata, file part named after `main_module`). Secrets are only ever read from a file (`--from-file`) — never pass a secret value as a command-line argument.
5. Reads need no confirmation. A 401/403 is a question about the request before it is a question about the token: check which verify endpoint applies (rule in Auth) and that the token's scopes cover the operation before concluding the token is bad. Never print, log, or persist the raw token; the CLI only ever handles surrogates.

## Files
- SKILL.md
- bin/cloudflare.py

## Maturity
✅ Live — this is the production version from a running Muse setup: zone/DNS reads and writes, Pages direct-upload deploys of a live website, Workers + KV + secrets + routes are all in daily use, and the token-verification rules above were diagnosed against the real API. Live-tested 2026-10-19. The `--confirm` write gate is enforced in the CLI in this catalog version.
