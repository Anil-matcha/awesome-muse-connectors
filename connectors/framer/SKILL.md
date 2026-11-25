---
name: "framer"
description: "Check a Framer project's Server API connection: verify the per-project API key with the official handshake. Trigger phrases: framer, framer api, framer project."
metadata: { "includeInPrompt": true }
tagline: "Verify a Framer project's Server API connection. Framer's Server API is WebSocket/SDK-only (there is no REST surface): the official framer-api npm package opens a long-lived connection to wss://api.framer.com/channel/headless-plugin with the header Authorization: Token <api_key>, keyed to one project. This connector's CLI performs that same official handshake as a connection check, so auth proves the API key and project pair work."
catalog_auth: "per-project API key via the secure credential flow"
catalog_hosts: ["api.framer.com"]
---

# Framer

## Purpose
Verify a Framer project's Server API connection. Framer's Server API is WebSocket/SDK-only (there is no REST surface): the official `framer-api` npm package opens a long-lived connection to `wss://api.framer.com/channel/headless-plugin` with the header `Authorization: Token <api_key>`, keyed to one project. This connector's CLI performs that same official handshake as a connection check, so `auth` proves the API key and project pair work.

## Tooling
All commands go through `bin/framer.py`:

```bash
bin/framer.py auth --project "https://framer.com/projects/Sites--aabbccddeeff00112233"
    # verify the API key against a project (accepts a project URL or a bare project id)
```

A successful `auth` prints the handshake result (session id, mode, active branch). Deeper operations (pages, CMS collections and items, canvas nodes, asset uploads, preview deploys, production deploys, redirects) run through the official `framer-api` npm package (`npm i framer-api`), not through this CLI: the plugin RPC protocol behind the socket is not reimplemented here.

## Auth
- Provider id: `framer` (credential is collected as `custom.framer`)
- Collection: per-project API key via the secure credential flow (`credentials.request_api_access`); create it under Site Settings > General in the Framer project. The key works for that one project only.
- Required scopes: n/a (project-scoped key)
- Allowed hosts: `api.framer.com` (WebSocket only: `wss://api.framer.com/channel/headless-plugin`)
- Status check: `bin/framer.py auth --project <project url or id>`
- Transport detail (verified from the official `framer-api` package source, v5.0.0): the API key travels as the `Authorization: Token <api_key>` header on the WebSocket upgrade request, with the project id as a query parameter; there is no Bearer prefix and no REST endpoint to call.

## Operating Rules
1. The key is bound to one project: pass that project's URL or id to every command.
2. Publishing to production, deleting CMS items, and editing canvas nodes are confirmation-worthy writes; prefer preview deployments and CMS/page operations, and confirm before anything that changes the live site.
3. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/framer.py

## Maturity
🧪 Draft: host and auth transport pinned from the official `framer-api` package source (v5.0.0); the handshake client is new code and has not been run against Framer's servers yet. Full page/CMS/publish operations are intentionally out of scope for the CLI (see Purpose).
