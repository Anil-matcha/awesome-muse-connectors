---
name: "tiktok"
description: "Read TikTok via API v2: your profile and video list. Posting is approval-gated and not shipped. Trigger phrases: tiktok, my tiktok, tiktok profile, tiktok videos."
metadata: { "includeInPrompt": true }
tagline: "Read your TikTok profile and video list. API access needs TikTok app approval first, and posting is not shipped."
catalog_auth: "OAuth 2.0 (per-user; TikTok app approval required)"
catalog_hosts: ["open.tiktokapis.com"]
---

# TikTok

## Purpose
Read TikTok through the TikTok API v2: the authorized user's profile and their video list with view/like/comment counts. **Approval-gated platform, read-only by design:** TikTok requires app review and approval before API access works at all, and most apps cannot post videos without additional TikTok approval. This connector therefore ships only `auth`, `me`, and `videos`. There is no video-post command, and posting must never be claimed to work until a live call against an approved app proves it. Reach for this when the user wants to look at their TikTok profile or video stats from chat.

## Tooling
All commands go through `bin/tiktok.py` (read-only):

```bash
bin/tiktok.py auth                    # verify the OAuth token
bin/tiktok.py me                      # authorized user's profile
bin/tiktok.py videos --limit 20       # list the user's videos with stats
bin/tiktok.py videos --limit 20 --cursor CURSOR   # next page
```

## Auth
- Provider id: `tiktok` (credential is collected as `custom.tiktok`)
- Collection: OAuth 2.0 via the secure credential flow (`credentials.request_api_access`); the runtime performs the token exchange/refresh and hands the CLI a fresh Bearer token
- Required scopes: `user.info.basic`, `video.list`. Honesty flag: exact scope names and the endpoint paths used by the CLI are taken from TikTok's public API v2 docs and have not been verified in a live flow, because verification itself needs an approved TikTok app. Treat them as provisional until a live call succeeds.
- Allowed hosts: `open.tiktokapis.com`
- Status check: `bin/tiktok.py auth`

## Operating Rules
1. **Check app review before blaming the credential.** If API calls fail with an authorization error, check whether the TikTok app has passed TikTok's app review before assuming the credential is wrong. Surface app-review status explicitly before debugging further.
2. **No posting command is shipped.** Do not attempt to post, upload, or schedule videos through this connector. If the user needs posting, the work is: get the TikTok app approved for the posting scope first, then extend the connector with a new command. Never tell the user posting works when it has not been proven.
3. `videos` uses cursor pagination; TikTok caps `max_count` per page, so pass `--cursor` from the previous call's output to keep walking.
4. All commands are read-only and need no confirmation.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/tiktok.py`). Do not print, log, or transmit the token.

## Files
- SKILL.md
- bin/tiktok.py

## Maturity
Draft: written from TikTok's public API v2 docs; scope names and paths unconfirmed because verification needs an approved TikTok app.
