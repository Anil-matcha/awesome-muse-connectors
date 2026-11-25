---
name: "bluesky"
description: "Read and write Bluesky: view profiles and timelines, search posts, post, follow, read notifications. Trigger phrases: bluesky, atproto."
metadata: { "includeInPrompt": true }
tagline: "Read timelines, search posts, post and follow."
catalog_auth: "App password (per-account; session-based)"
catalog_hosts: ["bsky.social"]
---

# Bluesky

## Purpose
Read and write the user's Bluesky account through the AT Protocol (XRPC): view profiles and the home timeline, search posts, create posts, follow accounts, and list notifications. Use when the user mentions Bluesky or atproto.

## Tooling
All commands go through `bin/bluesky.py`. Every command takes a required `--handle` (the account handle, e.g. `me.bsky.social`):

```bash
bin/bluesky.py auth --handle me.bsky.social                  # verify the session
bin/bluesky.py profile --handle me.bsky.social               # view a profile (add --target to view someone else)
bin/bluesky.py timeline --handle me.bsky.social              # home timeline
bin/bluesky.py search --handle me.bsky.social --query "agents"  # search posts
bin/bluesky.py post --handle me.bsky.social --text "hello world"  # publish a post (confirm first)
bin/bluesky.py follow --handle me.bsky.social --target them.bsky.social  # follow an account (confirm first)
bin/bluesky.py notifications --handle me.bsky.social         # list notifications
```

The CLI resolves the account's PDS automatically (via `resolveHandle` + the DID document), caches the session at `.bluesky-session.json` next to the skill, and refreshes tokens transparently on 401.

## Auth
- Provider id: `bluesky` (credential is collected as `custom.bluesky`)
- Collection: a Bluesky app password via the secure credential flow (`credentials.request_api_access`); created in the Bluesky app under Settings > App passwords. Use an app password only, never the main account password.
- Allowed hosts: `bsky.social`, `public.api.bsky.app`, `plc.directory`, plus the account's resolved PDS host (added at runtime after resolution)
- Status check: `bin/bluesky.py auth --handle <your-handle>` (must return `"ok": true`)

## Operating Rules
1. `post` and `follow` are writes: confirm the exact text or target handle with the user before running, unless standing permission exists.
2. Reading (profile, timeline, search, notifications) needs no confirmation.
3. The session manager reuses cached tokens and refreshes on 401; it never calls `createSession` more than needed (rate cap 30/5min). Do not hammer endpoints; respect atproto rate-limit points.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/bluesky.py

## Maturity
🧪 Draft: written from the AT Protocol's public API docs; not yet live-tested end-to-end.
