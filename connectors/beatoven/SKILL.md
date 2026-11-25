---
name: "beatoven"
description: "Beatoven.ai royalty-free music generation: compose tracks, poll tasks, download audio, fetch individual stems. Trigger phrases: beatoven, compose music, generate a track, royalty free music, background music."
metadata: { "includeInPrompt": true }
tagline: "Beatoven.ai royalty-free music generation: compose tracks, poll tasks, download audio, fetch individual stems."
catalog_auth: "API token via the secure credential flow"
catalog_hosts: ["public-api.beatoven.ai"]
---

# Beatoven.ai

## Purpose
Compose royalty-free music with Beatoven's public composition API: text-to-music (also audio-to-music and video-to-music prompts), task polling, track download, and individual stems (bass, chords, melody, percussion), plus SFX via the maestro model. Beatoven is Fairly Trained certified (licensed training data), so output is commercially safe, and it is the only verified self-serve music API in the catalog (Suno and Udio have no public APIs). Also available on the fal.ai marketplace.

## Tooling
All commands go through `bin/beatoven.py`:

```bash
bin/beatoven.py auth                                                      # verify credential setup (no spend)
bin/beatoven.py compose --prompt "30 seconds peaceful lo-fi chill hop track" --format wav
bin/beatoven.py compose --prompt "upbeat podcast intro" --format mp3 --looping
bin/beatoven.py status --task-id <task_id>                                # poll until composed
bin/beatoven.py download --task-id <task_id> --out track.wav              # download the composed track
bin/beatoven.py download --url https://.../track.wav --out track.wav      # download from a track URL directly
bin/beatoven.py stems --task-id <task_id>                                 # list the four stem URLs
bin/beatoven.py stems --task-id <task_id> --stem bass --out bass.wav      # download one stem
```

`compose` starts an async task and prints a `task_id`. Poll `status` with backoff; when status is `composed`, the response carries `track_url` and `stems_url` (bass, chords, melody, percussion). Endpoint paths are from Beatoven's published api-spec.md.

## Auth
- Provider id: `beatoven` (credential is collected as `custom.beatoven`)
- Collection: API token via the secure credential flow (`credentials.request_api_access`); created in the Beatoven developer dashboard
- Allowed hosts: `public-api.beatoven.ai` (plus the download host Beatoven's own task response returns)
- Status check: `bin/beatoven.py auth` (must return `"ok": true`). The token is sent verbatim as `Authorization: Bearer <token>`, per Beatoven's published API spec.

## Operating Rules
1. Compositions are metered. Confirm with Michael before every `compose`, stating the prompt and format, plus whether looping is on.
2. Track and stem URLs come back in the composed task response; `download` fetches them to a local file. Never store the URL as the finished artifact.
3. Output formats: mp3, aac, wav. The default in this CLI is wav.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/beatoven.py`). Do not print, log, or transmit the token.

## Files
- SKILL.md
- bin/beatoven.py

## Maturity
🧪 Draft: written from Beatoven's published API spec via the research dossier; not yet live-tested end-to-end.
