---
name: "slack"
description: "Read and write Slack: list channels, read history, post messages, search, list users. Trigger phrases: slack, slack channel, post to slack."
metadata: { "includeInPrompt": true }
tagline: "Read channels, post messages, list users. The most-requested workplace connector."
catalog_auth: "Slack OAuth (per-user)"
catalog_hosts: ["slack.com"]
---

# Slack

## Purpose
Read and write the user's Slack workspace: list channels, read recent history, post messages, search messages, list users. Use when the user mentions Slack or wants something sent to / found in a Slack channel.

## Tooling
All commands go through `bin/slack.py`:

```bash
bin/slack.py auth                                        # verify the connection (auth.test)
bin/slack.py channels                                    # list channels (public + private)
bin/slack.py history --channel C0123456789 --limit 20    # recent messages in a channel
bin/slack.py post --channel C0123456789 --text "hello"    # post a message
bin/slack.py users                                       # list workspace users
bin/slack.py search --query "deploy"                     # search messages (needs search:read on the token)
```

Channel arguments accept channel IDs (`C...`). Use `channels` to resolve a `#name` to its ID first.

## Auth
- Provider id: `slack` (credential is collected as `custom.slack`)
- Collection: provider OAuth via the secure credential flow (`credentials.request_api_access`)
- Required scopes: `channels:read`, `channels:history`, `groups:read`, `groups:history`, `chat:write`, `users:read`
- Granting more scopes: the install requests the minimum above so setup always succeeds, but nothing locks you to that set. Add any bot scopes your Slack app needs (OAuth & Permissions in your app settings), then reconnect: the CLI never checks scopes itself, it calls the API with whatever your token carries and reports Slack's own errors when a scope is missing.
- `search:read` only exists on user tokens: Slack never grants it to bot tokens, and the provider OAuth install used here issues bot tokens. The `search` command is included anyway; when the token lacks the scope it exits with exact instructions on what to add instead of a raw error. Requesting `search:read` as a bot scope makes Slack reject the whole install ("Invalid permissions requested"), so it stays out of the default set.
- Allowed hosts: `slack.com`
- Status check: `bin/slack.py auth` (must return `"ok": true`)

## Operating Rules
1. `post` is a write: confirm the exact text and destination channel with the user before sending, unless standing permission to post exists.
2. Reading (channels, history, users, search) needs no confirmation.
3. Slack rate-limits aggressively on bursts; if a call returns `ratelimited`, wait the `Retry-After` seconds and continue. Do not hammer.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/slack.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/slack.py

## Maturity
✅ Live-tested: installed from a raw URL and exercised against the real Slack API (auth, channels, users, history, post all verified; private-channel scopes untestable, this workspace has no private channels).
