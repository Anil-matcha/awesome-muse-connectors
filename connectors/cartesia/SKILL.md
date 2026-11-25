---
name: "cartesia"
description: "Cartesia text-to-speech: synthesize speech audio and browse voices. Trigger phrases: cartesia, text to speech, TTS, synthesize voice, voiceover."
metadata: { "includeInPrompt": true }
tagline: "Generate spoken audio from text with Cartesia's Sonic models (40+ languages) and browse the Cartesia voice library. Reach for this when the user wants narration, voiceovers, or spoken-audio files produced from a script."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.cartesia.ai"]
---

# Cartesia

## Purpose
Generate spoken audio from text with Cartesia's Sonic models (40+ languages) and browse the Cartesia voice library. Reach for this when the user wants narration, voiceovers, or spoken-audio files produced from a script.

## Tooling
All commands go through `bin/cartesia.py`. Every request automatically sends the required date header `Cartesia-Version: 2026-08-14`.

```bash
bin/cartesia.py auth
# {"ok": true, "voices": 60} on success

bin/cartesia.py voices
# list available voices (id, name, language)

bin/cartesia.py voice-get --id <VOICE_ID>
# details for a single voice

bin/cartesia.py tts --text "Hello world" --voice-id <VOICE_ID> --out narration.wav
# synthesize speech to a local WAV file; prints the saved path

bin/cartesia.py tts --text "Bonjour le monde" --voice-id <VOICE_ID> \
    --language fr --model-id sonic-3 --out fr.wav
```

Notes:
- `tts` returns audio binary. The CLI writes it to `--out` (default `cartesia-output.wav`) and prints the resulting path.
- Streaming TTS (`POST /tts/sse`) and the WebSocket TTS/STT surfaces are real-time and outside CLI scope.

## Auth
- Provider id: `cartesia` (credential is collected as `custom.cartesia`)
- Collection: Cartesia API key (`sk_car_...`) via the secure credential flow (`credentials.request_api_access`); create one at play.cartesia.ai/keys
- Allowed hosts: `api.cartesia.ai`
- Connect placement: `bearer_header` (the key goes in `Authorization: Bearer <key>`)
- The API also requires the date header `Cartesia-Version: 2026-08-14` on every request; the CLI sends it for you.
- Status check: `bin/cartesia.py auth`

## Operating Rules
1. TTS synthesis is credit-metered. Every `tts` call spends Cartesia credits, so synthesize only what the user asked for and batch long scripts into as few calls as possible.
2. **Voice creation and voice cloning are confirmation-gated**: confirm with the user before creating or cloning any voice. This draft CLI does not ship a clone command; use the Cartesia dashboard or SDK for cloning.
3. Never use API keys in client-side code. The connector only ever handles the surrogate, never the raw key.
4. The CLI pins `Cartesia-Version: 2026-08-14`. Treat a version bump like a dependency upgrade and do not change the date casually.

## Files
- SKILL.md
- bin/cartesia.py

## Maturity
🧪 Draft: written from Cartesia's public API docs with header and paths cross-checked against official docs at build time; not yet live-tested end-to-end. Voice create/clone and pronunciation dictionaries are not yet in the CLI.
