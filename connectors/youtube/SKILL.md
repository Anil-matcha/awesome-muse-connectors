---
name: "youtube"
description: "Work with YouTube: read channels, videos, search, playlist items; upload videos and post comments (with confirmation). Trigger phrases: youtube, videos, upload video, youtube comment."
metadata: { "includeInPrompt": true }
tagline: "Read channels and videos, search, plus uploads and comments with confirmation."
catalog_auth: "OAuth 2.0 (per-user)"
catalog_hosts: ["www.googleapis.com"]
---

# YouTube

## Purpose
Read public YouTube data (channels, videos with stats, search, playlist items) and write to the authenticated user's channel: upload video files and post top-level comments. Use when the user mentions YouTube or videos.

## Tooling
All commands go through `bin/youtube.py`:

```bash
bin/youtube.py auth                                     # verify the OAuth token
bin/youtube.py channel --id UC_abc123                   # show a channel
bin/youtube.py video --id dQw4w9WgXcQ                  # show a video
bin/youtube.py search --query "repair cafe" --limit 10 # search videos
bin/youtube.py playlist-items --playlist-id PL_abc123 --limit 25  # list playlist items

bin/youtube.py upload --file demo.mp4 --title "Demo" --description "..." \
    --privacy private \
    --confirm 'upload "demo.mp4" as private video "Demo"'
bin/youtube.py comment --video-id dQw4w9WgXcQ --text "Great build!" \
    --confirm 'post comment on video dQw4w9WgXcQ: "Great build!"'
```

The auth check uses the 1-unit `/channels?mine=true` endpoint, never the expensive search endpoint. `upload` does a resumable upload in one chunk (session init, then a single PUT of the file bytes); `--privacy` defaults to `private`. `comment` posts a top-level comment as the authenticated channel.

## Auth
- Provider id: `youtube` (credential is collected as `custom.youtube`)
- Collection: OAuth 2.0 via the secure credential flow (`credentials.request_api_access`); Google Cloud Console OAuth client with the YouTube Data API v3 enabled. The token is sent as `Authorization: Bearer <token>`.
- Required scopes: `https://www.googleapis.com/auth/youtube.readonly` (reads), `https://www.googleapis.com/auth/youtube.upload` (uploads), `https://www.googleapis.com/auth/youtube.force-ssl` (comments; this is the scope commentThreads.insert requires). If reads work but writes 403, re-approve with all three scopes.
- Allowed hosts: `www.googleapis.com`
- Status check: `bin/youtube.py auth` (must return `"ok": true`)
- Quota binding constraint: YouTube grants 10,000 quota units per day by default. `search` costs 100 units per call, a comment costs 50, and an upload costs ~1,600 (reported by secondary sources; not in Google's own docs — treat as approximate), so use them sparingly. Favor the 1-unit reads and cache results aggressively: do not re-run the same lookup twice in a session.

## Operating Rules
1. Reads (`auth`, `channel`, `video`, `search`, `playlist-items`) need no confirmation.
2. **Writes need exact-match confirmation on every call.** `upload` requires `--confirm` with the exact string the CLI echoes (names the file, the privacy setting, and the title) because it puts a video on the user's channel. `comment` requires `--confirm` with its echoed string (video ID plus the first 60 chars of the text) because the comment is public immediately.
3. Keep every upload `private` by default; only use `--privacy public` when the user explicitly asks.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/youtube.py

## Maturity
🧪 Draft: written from Google's public API docs; not yet live-tested end-to-end. The upload flow (resumable session + byte PUT) and comment path have not been verified in a live flow.
