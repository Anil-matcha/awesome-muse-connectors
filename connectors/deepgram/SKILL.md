---
name: "deepgram"
description: "Deepgram speech AI: transcribe audio to text and synthesize speech (TTS). Trigger phrases: deepgram, transcribe audio, speech to text, STT, deepgram tts."
metadata: { "includeInPrompt": true }
tagline: "Transcribe prerecorded audio files to text (with optional diarization, summaries, topics, sentiment) and synthesize speech with Deepgram's Aura voices. Reach for this when the user has an audio file to transcribe or wants spoken audio generated from text."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.deepgram.com"]
---

# Deepgram

## Purpose
Transcribe prerecorded audio files to text (with optional diarization, summaries, topics, sentiment) and synthesize speech with Deepgram's Aura voices. Reach for this when the user has an audio file to transcribe or wants spoken audio generated from text.

## Tooling
All commands go through `bin/deepgram.py`. Auth uses exactly `Authorization: Token <api_key>` (not Bearer); the CLI wires it through the credential surrogate.

```bash
bin/deepgram.py auth
# {"ok": true, "projects": 2} on success

bin/deepgram.py projects
# list Deepgram projects (id, name)

bin/deepgram.py transcribe --file meeting.wav
# upload a local audio file, print the transcript JSON

bin/deepgram.py transcribe --file call.mp3 --model nova-3 --diarize --summarize --topics --sentiment
# transcript with speaker labels plus summary, topics and sentiment

bin/deepgram.py tts --text "Thanks for listening." --out thanks.mp3
# synthesize with an Aura voice to a local MP3 file; prints the saved path
```

Notes:
- `transcribe` reads a local audio file, posts the bytes to `POST /v1/listen`, and prints the full transcript JSON. Content type is guessed from the file extension (wav, mp3, m4a, flac, ogg supported).
- `tts` posts `{"text": "..."}` to `POST /v1/speak?model=<model>&encoding=mp3` (default model `aura-2-thalia-en`, 2,000-char limit) and saves the audio to `--out` (default `deepgram-output.mp3`).
- Live WebSocket STT (`/v1/listen` streaming) is real-time and outside CLI scope.

## Auth
- Provider id: `deepgram` (credential is collected as `custom.deepgram`)
- Collection: Deepgram API key via the secure credential flow (`credentials.request_api_access`); create one in the Deepgram console
- Allowed hosts: `api.deepgram.com`
- Connect placement: `custom_header:Authorization` (the **stored credential value must be exactly `Token <api_key>`**, with the `Token ` prefix; Bearer is not accepted)
- Status check: `bin/deepgram.py auth`

## Operating Rules
1. Usage is metered by audio duration (transcription) and characters (TTS). Transcribe and synthesize only what the user asked for; confirm before processing large batches.
2. **API key and project management are confirmation-gated**: confirm with the user before creating, rotating, or deleting keys or projects. This draft CLI is read/compute only; it does not manage keys or projects.
3. The transcript JSON can contain full conversation text. Treat transcripts as the user's private content; do not republish or forward them without instruction.
4. Never log or print the raw key; the CLI only ever handles the surrogate.

## Files
- SKILL.md
- bin/deepgram.py

## Maturity
🧪 Draft: written from Deepgram's public API docs with paths cross-checked at build time; not yet live-tested end-to-end. Key/project management and usage endpoints are not yet in the CLI.
