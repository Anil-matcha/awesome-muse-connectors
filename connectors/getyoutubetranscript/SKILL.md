---
name: "getyoutubetranscript"
description: "Read YouTube videos as text: full transcripts in any caption language, caption languages, YouTube search, a channel's latest videos and playlist videos. Trigger phrases: youtube transcript, video transcript, what did this video say, summarize this youtube video, captions."
metadata: { "includeInPrompt": true }
tagline: "YouTube transcripts in any caption language, plus video search, channel and playlist listings. Read-only."
catalog_auth: "GetYouTubeTranscript API key (per-user, getyoutubetranscript.com/developers)"
catalog_hosts: ["getyoutubetranscript.com"]
---

# GetYouTubeTranscript

## Purpose
Read-only access to YouTube as text through the GetYouTubeTranscript REST API (https://getyoutubetranscript.com/docs, checked 2026-11-20): the full transcript of a video in any caption language it has (optionally as timed segments), the list of caption languages, YouTube search, a channel's latest videos, and the videos in a playlist. Use when the user shares a YouTube link and wants it summarized, quoted or searched, or wants transcripts for a channel or playlist. It complements the `youtube` connector, which reads metadata through the YouTube Data API but cannot fetch transcripts of other channels' videos.

## Tooling
All commands go through `bin/getyoutubetranscript.py`:

```bash
bin/getyoutubetranscript.py auth                                          # verify the key (free call)
bin/getyoutubetranscript.py transcript --video https://youtu.be/jNQXAC9IVRw   # full transcript text
bin/getyoutubetranscript.py transcript --video jNQXAC9IVRw --language en --timestamps  # timed segments
bin/getyoutubetranscript.py languages --video jNQXAC9IVRw                 # caption languages available
bin/getyoutubetranscript.py search --query "solar panel install" --limit 5  # search videos
bin/getyoutubetranscript.py channel-latest --channel @mkbhd               # a channel's latest videos
bin/getyoutubetranscript.py playlist --playlist PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI  # playlist videos
```

`--video` accepts a full or short YouTube URL or the 11-character video ID. `playlist` returns a `continuation` token when there are more videos; pass it back with `--continuation` for the next page.

## Auth
- Provider id: `getyoutubetranscript` (credential is collected as `custom.getyoutubetranscript`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Get a key: getyoutubetranscript.com/developers (new accounts get 100 credits)
- Allowed hosts: `getyoutubetranscript.com`
- Status check: `bin/getyoutubetranscript.py auth` (must return `"ok": true`; it calls `GET /credits`, which costs nothing)
- Connect placement: `custom_header:x-api-key`

## Operating Rules
1. This connector is read-only: it only fetches transcripts and public YouTube listings. It never writes, posts, or changes anything.
2. Each successful call except `auth` uses 1 credit from the user's account; failed calls are not charged. Fetch a transcript once per video per session and reuse it rather than calling again.
3. Errors come back as `HTTP <code>: <CODE>: <message>` (for example 404 `VIDEO_UNAVAILABLE`, 401 invalid key, 402 no credits left, 429 rate limited). Report them to the user; do not retry 401 or 402.
4. Quote transcripts as returned; do not invent words that are not in the transcript. Auto-generated captions (`caption_type` auto) can contain recognition errors, so say so when quoting them.
5. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/getyoutubetranscript.py

## Maturity
🧪 Draft: every command was run against the live API on 2026-11-20 with a real key (auth, transcript with and without timestamps, languages, search, channel-latest, playlist, and the 404 error path), using a local stand-in for the Muse credential helper. Not yet run inside a Muse runtime.
