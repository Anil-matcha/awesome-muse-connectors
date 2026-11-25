---
name: "elevenlabs"
description: "ElevenLabs: check subscription usage, list voices, and generate text-to-speech audio. TTS spends quota and needs --confirm. Trigger phrases: elevenlabs, eleven labs, voice api, tts, text to speech."
metadata: { "includeInPrompt": true }
tagline: "Check ElevenLabs subscription usage, list voices, and generate text-to-speech audio (TTS needs --confirm, spends characters)."
catalog_auth: "ElevenLabs API key (per-user, elevenlabs.io/app/settings/api-keys)"
catalog_hosts: ["api.elevenlabs.io"]
---

# ElevenLabs

## Purpose
Work with the user's ElevenLabs account: subscription tier and character usage (`me`), the voices available on the account (`voices`), and text-to-speech generation (`text-to-speech`). TTS consumes characters from the account quota (real money on paid plans): it requires the exact-match `--confirm` string on every generation, stating the voice and character count.

## Tooling
All commands go through `bin/elevenlabs.py`:

```bash
bin/elevenlabs.py me        # subscription tier, character_count, character_limit
bin/elevenlabs.py voices    # available voices (name, category)

# TTS: every generation requires the exact --confirm string the CLI prints
bin/elevenlabs.py text-to-speech --text "Hello there" --voice-name Rachel --out /tmp/line.mp3
bin/elevenlabs.py text-to-speech --text "Hello there" --voice-id VOICE_ID --out /tmp/line.mp3
bin/elevenlabs.py text-to-speech --text "Hello" --voice-name Rachel --out /tmp/line.mp3 --voice-settings '{"stability":0.5,"similarity_boost":0.75}'
```

`--voice-id` wins over `--voice-name`. Audio saves to `--out` (MP3). Default model is `eleven_multilingual_v2`.

## Auth
- Provider id: `elevenlabs` (credential is collected as `custom.elevenlabs`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`): create one at elevenlabs.io/app/settings/api-keys
- Connect placement: `custom_header:xi-api-key` (ElevenLabs uses `xi-api-key`, not `Authorization: Bearer`)
- Allowed hosts: `api.elevenlabs.io`
- Status check: `bin/elevenlabs.py me` (a successful response proves the key works)

## Operating Rules
1. COST WARNING: `text-to-speech` spends characters from the account quota, which costs real money on paid plans. Check `me` first to confirm headroom, and confirm with the user before every generation, stating the voice and character count. Every generation requires the exact-match `--confirm` string the CLI prints; never skip it.
2. The `me` and `voices` reads are free and need no confirmation.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/elevenlabs.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/elevenlabs.py

## Maturity
🧪 Draft: written from ElevenLabs' public API docs; not yet live-tested end-to-end. The `text-to-speech` endpoint path and body are doc-built only and have never been run against a real account.
