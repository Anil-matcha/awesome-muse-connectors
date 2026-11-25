---
name: "playht"
description: "PlayHT text-to-speech: synthesize speech, list voices, and manage instant voice clones. Trigger phrases: playht, play ht, text to speech, TTS, voice clone."
metadata: { "includeInPrompt": true }
tagline: "Generate spoken audio from text with PlayHT voices, browse stock and cloned voices, and create instant voice clones. Reach for this when the user wants narration or voiceovers, a voice library lookup, or a voice cloned from a sample."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.play.ht"]
---

# PlayHT

## Purpose
Generate spoken audio from text with PlayHT voices, browse stock and cloned voices, and create instant voice clones. Reach for this when the user wants narration or voiceovers, a voice library lookup, or a voice cloned from a sample.

## Tooling
All commands go through `bin/playht.py`. PlayHT uses a single uppercase `AUTHORIZATION: Bearer <key>` header (older dual-header docs are stale); the CLI wires it through the credential surrogate.

```bash
bin/playht.py auth
# {"ok": true, "voices": 120} on success

bin/playht.py voices
# list stock voices (id, name, language, gender)

bin/playht.py tts --text "Welcome to the show." --voice-id <VOICE_ID> --out show.mp3
# streaming synthesis to a local MP3 file; prints the saved path

bin/playht.py clones
# list your cloned voices

bin/playht.py clone --json clone-body.json
# create an instant voice clone; body follows the current PlayHT docs
# for POST /api/v2/cloned-voices/instant/ (confirmation-gated)
```

Notes:
- `tts` returns audio binary. The CLI writes it to `--out` (default `playht-output.mp3`) and prints the resulting path. Max 20,000 characters per request; PlayHT rate-limits to 120 requests/min per key.
- Batch synthesis jobs are credit-consuming and confirmation-gated; they are not in this draft CLI.

## Auth
- Provider id: `playht` (credential is collected as `custom.playht`)
- Collection: PlayHT API key via the secure credential flow (`credentials.request_api_access`); generate one under Settings, then API, in the PlayHT dashboard
- Allowed hosts: `api.play.ht`
- Connect placement: `custom_header:AUTHORIZATION` (uppercase; the **stored credential value must include the `Bearer ` prefix**, since the helper places the header value verbatim: `AUTHORIZATION: Bearer <key>`)
- Status check: `bin/playht.py auth`

## Operating Rules
1. Synthesis is credit-metered and rate-limited (120 req/min, 20,000 chars/request). Keep `tts` calls within the character cap; split long scripts before calling.
2. **Voice cloning and batch synthesis are confirmation-gated**: confirm with the user before running `clone` or any batch job. Only clone voices the user has the right to clone.
3. Never log or print the raw key; the CLI only ever handles the surrogate.
4. Ignore older PlayHT docs that describe a dual-header scheme (`Authorization` + `X-USER-ID`); the current API uses the single uppercase `AUTHORIZATION` header.

## Files
- SKILL.md
- bin/playht.py

## Maturity
🧪 Draft: written from PlayHT's current public docs with paths cross-checked at build time; not yet live-tested end-to-end. TTS jobs (async batch synthesis) are not yet in the CLI.
