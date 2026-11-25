---
name: "mastodon"
description: "Read and write Mastodon: verify the account, list own posts and followers, publish toots with native scheduling, upload media. Trigger phrases: mastodon, toot, post to mastodon, fediverse."
metadata: { "includeInPrompt": true }
tagline: "Read and write Mastodon: verify the account, list own posts and followers, publish toots with native scheduling, upload media."
catalog_auth: "provider OAuth via the secure credential flow"
catalog_hosts: ["your Mastodon instance host", "declared at connect time. The credential is only ever sent to that host"]
---

# Mastodon

## Purpose
Read and write the user's Mastodon account: verify the connection, list own toots, list followers, publish toots (with native scheduling via `scheduled_at`), upload media for toots. Use when the user mentions Mastodon or the fediverse.

## Tooling
All commands go through `bin/mastodon.py`:

```bash
bin/mastodon.py verify --host https://mastodon.social                                  # verify the token (own profile)
bin/mastodon.py my-posts --host https://mastodon.social --limit 20                     # recent toots
bin/mastodon.py followers --host https://mastodon.social --limit 20                    # own followers
bin/mastodon.py post --host https://mastodon.social --text "hello"                     # confirm first
bin/mastodon.py post --host https://mastodon.social --text "later" --scheduled-at "2026-09-17T09:00:00Z" --visibility unlisted
bin/mastodon.py media-upload --host https://mastodon.social --file ./pic.png --description "alt text"  # returns a media id for post --media-ids
```

## Auth
- Provider id: `mastodon` (credential is collected as `custom.mastodon`)
- Collection: provider OAuth via the secure credential flow (`credentials.request_api_access`). Fully self-serve: register an app on your own instance with `POST /api/v1/apps`, or generate a personal token under Settings > Development on your instance.
- Required scopes: `read`, `write`, `follow`, `push` (granular scopes such as `write:statuses` also work)
- Allowed hosts: your Mastodon instance host, declared at connect time (the `--host` you pass, e.g. `https://mastodon.social`; it must start with `http://` or `https://`). The credential is only ever sent to that host.
- Status check: `bin/mastodon.py verify --host <your-instance>` (must return `"ok": true`)

## Operating Rules
1. `post` is a public write: confirm the text and visibility, plus any attachments, with the user before publishing, unless standing permission exists. Scheduled toots go out unattended, so confirm those too.
2. Toots are limited to 500 characters; the CLI rejects anything longer rather than truncating, so keep posts short or split them.
3. Instance rules apply: label bot accounts where your instance asks, and note that some instances disable open app registration.
4. Reading (verify, my-posts, followers, media-upload) needs no confirmation.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/mastodon.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/mastodon.py

## Maturity
🧪 Draft: written from Mastodon's public API docs via the verified research dossier; not yet live-tested end-to-end.
