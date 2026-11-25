---
name: "restream"
description: "Manage Restream multistreaming: profile, streaming destinations, channel metadata, and stream key. Trigger phrases: restream, livestream destinations, multistream, stream key, toggle destination."
metadata: { "includeInPrompt": true }
tagline: "Manage Restream multistreaming: read your profile, list streaming destinations (channels), toggle destinations or edit channel metadata, and retrieve your stream key. Use when the user wants to control where a livestream goes without opening the Restream dashboard."
catalog_auth: "provider OAuth 2.0 via the secure credential flow"
catalog_hosts: ["api.restream.io"]
---

# Restream

## Purpose
Manage Restream multistreaming: read your profile, list streaming destinations (channels), toggle destinations or edit channel metadata, and retrieve your stream key. Use when the user wants to control where a livestream goes without opening the Restream dashboard.

## Tooling
All commands go through `bin/restream.py`:

```bash
bin/restream.py auth                                  # verify the OAuth token
bin/restream.py profile                               # show your Restream profile
bin/restream.py channels                              # list streaming destinations
bin/restream.py channel-update --id CH_ID \
    --payload '{"active": false}'                      # toggle a destination (confirm first)
bin/restream.py channel-meta-get --id CH_ID           # get a channel's metadata
bin/restream.py channel-meta-update --id CH_ID \
    --payload '{"title": "New title"}'                 # edit metadata (confirm first)
bin/restream.py stream-key                            # show your stream key (output is a live secret)
```

Live chat runs over a real-time WebSocket (`wss://chat.api.restream.io/ws`) and is intentionally out of CLI scope: the CLI cannot hold a persistent chat socket, so reading or sending chat is not supported here.

## Auth
- Provider id: `restream` (credential is collected as `custom.restream`)
- Collection: provider OAuth 2.0 (authorization-code) via the secure credential flow (`credentials.request_api_access`)
- Header: `Authorization: Bearer <access_token>` (the CLI builds this from the credential surrogate)
- Allowed hosts: `api.restream.io`
- Status check: `bin/restream.py auth` (reads your profile; a successful read proves the token works)

## Operating Rules
1. **Confirm before `channel-update` or `channel-meta-update`**: these toggle destinations and change what is live. Name the channel and the exact change.
2. **Confirm before anything that changes the stream key**: rotating it disconnects every active encoder using the old key. Reads are fine, but treat the output as a live secret; never paste it into chat, logs, or tickets.
3. Chat is WebSocket-only and out of scope; do not try to poll chat over REST.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/restream.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/restream.py

## Maturity
Draft: written from Restream's public API docs; not yet live-tested end-to-end.
