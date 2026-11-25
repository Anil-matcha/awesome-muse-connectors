---
name: "spotify"
description: "Work with Spotify: read your profile, playlists, top tracks and artists, search the catalog, and (with confirmation) create playlists, add tracks, and save tracks to your library. Trigger phrases: spotify, my playlists, my top tracks, top artists, save track, search spotify."
metadata: { "includeInPrompt": true }
tagline: "Read your profile, playlists, top tracks and artists, and search the catalog. Playlist and library writes need your confirmation."
catalog_auth: "OAuth 2.0 Authorization Code (per-user)"
catalog_hosts: ["api.spotify.com"]
---

# Spotify

## Purpose
Work with the Spotify Web API: read the current user's profile, playlists, playlist tracks, and top tracks/artists; search the Spotify catalog; and (each behind an exact-match confirmation) create playlists, add tracks to playlists, and save tracks to the user's library. Reach for this when the user wants to look at or curate their Spotify content from chat.

## Tooling
All commands go through `bin/spotify.py`:

```bash
bin/spotify.py auth                                # verify the OAuth token
bin/spotify.py me                                  # current user's profile
bin/spotify.py playlists --limit 50                # list the user's playlists
bin/spotify.py playlist-tracks --playlist-id PID   # tracks in a playlist
bin/spotify.py top-tracks --limit 10               # user's top tracks
bin/spotify.py top-artists --limit 10              # user's top artists
bin/spotify.py search --query "khruangbin"          # search the catalog
bin/spotify.py playlist-create --name "Focus" \
    --confirm 'create playlist "Focus"'            # new playlist (private unless --public)
bin/spotify.py playlist-add --playlist-id PID \
    --uris "spotify:track:AAA,spotify:track:BBB" \
    --confirm "add 2 track(s) to playlist PID"     # append tracks
bin/spotify.py save-track --ids "AAA,BBB" \
    --confirm "save track(s) AAA,BBB to your library"  # save to Liked Songs
```

`--time-range` on the top commands takes `short_term`, `medium_term` (default), or `long_term`.

## Auth
- Provider id: `spotify` (credential is collected as `custom.spotify`)
- Collection: OAuth 2.0 Authorization Code flow via the secure credential flow (`credentials.request_api_access`); the runtime performs the token exchange/refresh and hands the CLI a fresh Bearer token
- Required scopes: `user-read-private`, `user-read-email`, `playlist-read-private`, `playlist-modify-private`, `playlist-modify-public`, `user-top-read`, `user-library-read`, `user-library-modify`. Honesty flag: this scope list is taken from Spotify's public Web API docs and has not been verified in a live flow; if a command returns 403, re-check the scopes granted at approval.
- Allowed hosts: `api.spotify.com`
- Status check: `bin/spotify.py auth`

## Operating Rules
1. **All writes need confirmation on every call.** `playlist-create`, `playlist-add`, and `save-track` refuse unless `--confirm` matches the exact string the CLI echoes (it names the playlist, track IDs, or library target). This is stricter than the standing first-use-only rule, chosen because these writes touch the user's personal library and are visible to other people when public.
2. `playlist-create` defaults to a private playlist; add `--public` only when the user explicitly asks for a public one.
3. Search and top-lists are read-only and need no confirmation.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/spotify.py`). Do not print, log, or transmit the token.

## Files
- SKILL.md
- bin/spotify.py

## Maturity
Draft: written from Spotify's public Web API docs; not yet live-tested end-to-end.
