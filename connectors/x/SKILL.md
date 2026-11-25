---
name: "x"
description: "Read and write X: post and delete tweets, search recent tweets, like tweets, send DMs. Trigger phrases: x, twitter, tweet."
metadata: { "includeInPrompt": true }
tagline: "Post, search, like, DM. Note: no usable free read tier."
catalog_auth: "OAuth2 PKCE (per-user; paid read access)"
catalog_hosts: ["api.x.com"]
---

# X

## Purpose
Use the user's X account: post and delete tweets, search recent tweets, like tweets, and send DMs. Use when the user mentions X, Twitter, or tweets.

## Tooling
All commands go through `bin/x.py`:

```bash
bin/x.py auth                                     # verify the OAuth token
bin/x.py post --text "hello world"                # post a tweet
bin/x.py search --query "AI agents" --limit 10    # search recent tweets
bin/x.py like --tweet-id 1234567890              # like a tweet (resolves your user ID first)
bin/x.py dm --user-id 1234567890 --text "hello"  # send a DM
bin/x.py delete --tweet-id 1234567890            # delete a tweet
```

Liking a tweet needs your numeric user ID: the CLI resolves it via `/2/users/me` before calling `/2/users/{id}/likes`, so you never have to pass it yourself.

## Auth
- Provider id: `x` (credential is collected as `custom.x`)
- Collection: provider OAuth (OAuth2 PKCE) via the secure credential flow (`credentials.request_api_access`); authorize URL `https://x.com/i/oauth2/authorize`, token URL `https://api.x.com/2/oauth2/token`
- Required scopes: `tweet.read`, `tweet.write`, `users.read`, `like.read`, `like.write`, `dm.read`, `dm.write`, `offline.access`
- Allowed hosts: `api.x.com`
- Status check: `bin/x.py auth` (must return `"ok": true`)
- Cost warning: X has no usable free read tier. The free tier is write-only (about 500 posts a month, about 100 reads a month). Anything beyond basic writes needs a paid tier or the newer pay-per-use pricing (roughly $0.005 per read, $0.01 per post), which is the sane path for a personal assistant. Post and delete stay cheap under either plan.

## Operating Rules
1. `post`, `like`, `dm`, and `delete` are writes: confirm the exact text and target with the user before running, unless standing permission exists.
2. Reading (auth, search) needs no confirmation, but keep `search` usage modest: every search call is a billed read.
3. X rate-limits by endpoint and tier; back off on 429s.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/x.py

## Maturity
🧪 Draft: written from X's public API docs; not yet live-tested end-to-end.
