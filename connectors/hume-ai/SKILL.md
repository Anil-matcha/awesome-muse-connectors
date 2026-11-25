---
name: "hume-ai"
description: "Hume AI Octave TTS and EVI speech-to-speech configs: synthesize speech and manage EVI configs. Trigger phrases: hume, hume ai, octave tts, EVI config."
metadata: { "includeInPrompt": true }
tagline: "Synthesize speech with Hume's Octave TTS models and read EVI (Empathic Voice Interface) conversational configs. Reach for this when the user wants expressive TTS audio from text or wants to inspect an EVI voice-agent configuration."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.hume.ai"]
---

# Hume AI

## Purpose
Synthesize speech with Hume's Octave TTS models and read EVI (Empathic Voice Interface) conversational configs. Reach for this when the user wants expressive TTS audio from text or wants to inspect an EVI voice-agent configuration.

## Tooling
All commands go through `bin/hume-ai.py`. REST auth uses the `X-HUME-API-KEY` header (not Bearer); the CLI wires it through the credential surrogate.

```bash
bin/hume-ai.py auth
# {"ok": true, "configs": 3} on success

bin/hume-ai.py configs
# list EVI configs (id, name)

bin/hume-ai.py config-get --id <CONFIG_ID>
# one EVI config

bin/hume-ai.py tts --text "Take a breath." --voice "Ava Song" --out calm.mp3
# synthesize with Octave TTS; prints the saved audio path
```

Notes:
- `tts` sends `POST /v0/tts` with the text as an utterance and an optional Octave voice name. Audio (or the raw provider response when audio cannot be extracted) is written to `--out` (default `hume-output.mp3`); the CLI prints the resulting path.
- Live EVI sessions are real-time WebSockets and are outside CLI scope. EVI config changes and cloned voices are confirmation-gated (see Operating Rules); this draft CLI covers config list/get only.

## Auth
- Provider id: `hume-ai` (credential is collected as `custom.hume-ai`)
- Collection: Hume API key via the secure credential flow (`credentials.request_api_access`); create one in the Hume portal
- Allowed hosts: `api.hume.ai`
- Connect placement: `custom_header:X-HUME-API-KEY` (the key goes in `X-HUME-API-KEY`, exactly; not a Bearer header)
- Status check: `bin/hume-ai.py auth`

## Operating Rules
1. All usage is metered. Every `tts` call spends Hume credits; synthesize only what the user asked for.
2. **EVI config changes and cloned voices are confirmation-gated**: confirm with the user before creating, updating, or deleting an EVI config, or before cloning a voice. EVI 1 and EVI 2 are retired (support ended 2025-08-30); target EVI 3 or EVI 4-mini only.
3. Live EVI sessions run over WebSocket, which this CLI does not open. Learn EVI 3/4-mini config fields by reading configs only.
4. Never accept or log the raw key; the CLI only ever handles the surrogate.

## Files
- SKILL.md
- bin/hume-ai.py

## Maturity
🧪 Draft: written from Hume's public API docs with the Octave TTS path cross-checked at build time; not yet live-tested end-to-end. EVI config create/update and voices listing are not yet in the CLI.
