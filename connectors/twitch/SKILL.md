---
name: "twitch"
description: "Read and write Twitch via the Helix API: channel profile, follower stats, live stream status, past videos, channel title and game updates, clip creation. Trigger phrases: twitch, stream stats, stream followers, channel update."
metadata: { "includeInPrompt": true }
tagline: "Read and write Twitch via the Helix API: channel profile, follower stats, live stream status, past videos, channel title and game updates, clip creation."
catalog_auth: "provider OAuth via the secure credential flow"
catalog_hosts: ["api.twitch.tv"]
---

# Twitch

## Purpose
Read and write the user's Twitch channel through the Helix API: channel profile, follower count, live stream status and viewers, past broadcasts and clips, channel title/game updates, clip creation. Use when the user mentions Twitch or their stream.

## Tooling
All commands go through `bin/twitch.py`:

```bash
bin/twitch.py auth --client-id abc123xyz                              # verify the token (returns own profile)
bin/twitch.py user --client-id abc123xyz --login someuser             # channel profile (omit --login for own)
bin/twitch.py followers --client-id abc123xyz --broadcaster-id 12345  # follower count + recent followers
bin/twitch.py stream --client-id abc123xyz --user-login someuser      # live now? viewer count, title, game
bin/twitch.py videos --client-id abc123xyz --user-id 12345            # past broadcasts and clips
bin/twitch.py channel-update --client-id abc123xyz --broadcaster-id 12345 --title "New title" --game-id 509658  # confirm first
bin/twitch.py clip-create --client-id abc123xyz --broadcaster-id 12345  # confirm first
```

The `followers`, `videos`, `channel-update`, and `clip-create` commands need the numeric channel id: run `user` first to resolve a login to it.

## Auth
- Provider id: `twitch` (credential is collected as `custom.twitch`)
- Collection: provider OAuth via the secure credential flow (`credentials.request_api_access`). Self-serve: register an app in the Twitch Developer Console (the Twitch account needs 2FA enabled; there is no review gate). User tokens come from the authorization code flow at `https://id.twitch.tv/oauth2/authorize`; app-only tokens come from client credentials at `https://id.twitch.tv/oauth2/token`.
- Required scopes: `user:read:email`, `channel:read:subscriptions`, `channel:manage:broadcast`, `clips:edit`, `chat:write` (request only the scopes the commands you need require)
- Client id: every Helix call needs both `Authorization: Bearer` and a `Client-Id` header. The bearer token comes from the stored credential; the client id comes from your app registration and is passed with `--client-id` on every command.
- Allowed hosts: `api.twitch.tv`
- Status check: `bin/twitch.py auth --client-id <id>` (must return `"ok": true`)

## Operating Rules
1. `channel-update` and `clip-create` are writes: confirm the exact title/game or the clip request with the user before running, unless standing permission exists.
2. Reading (user, followers, stream, videos) needs no confirmation.
3. Twitch Helix is rate-limited to 800 points per minute on the standard app tier; back off on 429s.
4. There is no "schedule a stream" write endpoint: channel metadata updates are the publish-side surface here.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/twitch.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/twitch.py

## Maturity
🧪 Draft: written from Twitch's public Helix docs via the verified research dossier; not yet live-tested end-to-end.
