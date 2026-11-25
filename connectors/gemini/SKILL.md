---
name: "gemini"
description: "Google Gemini text generation (system instructions, tools, Maps grounding) plus media generation: Nano Banana and Imagen 4 images, Veo 3.1 video, TTS. Trigger phrases: gemini, generate text, nano banana, imagen, veo video, gemini tts."
metadata: { "includeInPrompt": true }
tagline: "Google Gemini text generation (system instructions, tool use, Maps grounding) plus media generation — Nano Banana and Imagen 4 images, Veo 3.1 video with download, TTS — with cost confirmation enforced in code before any billed call."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["generativelanguage.googleapis.com"]
---

# Gemini

## Purpose
Use Google's Gemini API for both text and media from one connector. Text: `generateContent` with system instructions and tool use — including Google Maps grounding for live place data. Media: Nano Banana image generation/editing, Imagen 4 images, Veo 3.1 video (async, with a real download step), and text-to-speech. Use when the user asks for Gemini text generation, grounded place data, or AI-generated images, video, or voiceover via Google.

Source: Google Gemini API documentation (ai.google.dev/gemini-api/docs), checked 2026-10-19. This version merges the earlier media-only Draft catalog entry with the text lane from a production deployment, and fixes three defects in the Draft: cost confirmation is now enforced in code (the Draft only documented it), Veo results can actually be downloaded (the Draft's docs said to download but shipped no download step), and input images get their real MIME type (the Draft labelled every input `image/png`).

## Tooling
All commands go through `bin/gemini.py`:

```bash
bin/gemini.py auth                                                        # status check: verify the key answers
bin/gemini.py models [--limit N]                                          # list models (name + display name)
bin/gemini.py generate --prompt "..." [--model gemini-flash-lite-latest] [--system "..."] [--tools '<json>']

# Media — every command REQUIRES --confirm-cost "<model> <estimate>" (enforced in code):
bin/gemini.py image --prompt "a ceramic fox" --out /tmp/fox --confirm-cost "gemini-2.5-flash-image ~$0.03"
bin/gemini.py image --prompt "make it night" --image ./fox.jpg --out /tmp/fox-night --confirm-cost "gemini-2.5-flash-image ~$0.03"
bin/gemini.py imagen --prompt "studio product shot" --count 2 --out /tmp/prod --confirm-cost "imagen-4.0-generate-001 ~$0.08 for 2 images"
bin/gemini.py video --prompt "a drone shot over a harbor" --confirm-cost "veo-3.1-generate-preview ~$3.20 for 8s"
bin/gemini.py op-status --op operations/abc123                            # poll the Veo operation
bin/gemini.py download --op operations/abc123 --out /tmp/harbor           # save the finished video (<out>.mp4)
bin/gemini.py tts --text "Hello there" --voice Kore --out /tmp/line --confirm-cost "gemini-2.5-flash-preview-tts ~$0.01"
```

Maps grounding: `generate --tools '[{"google_maps": {}}]'` returns live place data (hours, ratings, reviews, address, phone, busy times) with `groundingMetadata` citations, on the free tier. It does place data only — not transit routing, ETAs, or directions (for those, use a Maps Platform Routes/Geocoding connector such as this catalog's google-maps entry). `--json` merges extra fields into any media request.

## Auth
- Provider id: `gemini` (credential is collected as `custom.gemini`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in Google AI Studio (aistudio.google.com/apikey) or Google Cloud Console.
- Allowed hosts: `generativelanguage.googleapis.com`
- Status check: `bin/gemini.py auth` (must return `"ok": true`)

## Operating Rules
1. **Media generation spends real money and the CLI enforces confirmation.** `image`, `imagen`, `video`, and `tts` refuse to run without `--confirm-cost "<model> <estimated cost>"` naming the exact model billed. Get the user's confirmation in conversation first, stating model and expected cost; never pre-fill it. Typical prices (checked 2026-10-19): Veo 3.1 ~$0.40/sec, Veo 3.1 Fast ~$0.10/sec, Lite ~$0.05/sec; Imagen 4 ~$0.02–0.06/image; Nano Banana ~$0.02–0.04/image.
2. **Billing pitfall:** all media generation requires a billing-enabled Google Cloud project; free-tier media quota is 0, so calls without billing fail with quota errors that look like auth problems. Text `generate` works on the free tier.
3. **Shared-quota caution:** a Gemini API key on a consumer Google AI plan draws from the same quota pool as other Gemini surfaces on that account (CLI tools, agent harnesses). Heavy media or text use here can starve those lanes, and vice versa; a 503/overloaded or quota error may be the pool, not this connector. When a model id 404s, check `models` — ids retire (for example `gemini-2.0-flash` is retired) and newer ids can be closed to new users.
4. Veo renders take minutes. Poll `op-status` with backoff; do not hammer it. Finish with `download` to actually save the video file.
5. A 401/403 is a question about the request before it is a question about the key — confirm the surrogate was attached. Never print, log, or persist the raw key; the CLI only ever handles surrogates.

## Files
- SKILL.md
- bin/gemini.py

## Maturity
✅ Live — merged production version: the text lane (generate with system instructions, tools, Maps grounding) runs daily in a running Muse setup, and the media commands were verified against the real API on 2026-10-19 (TTS generation completed with the enforced `--confirm-cost` gate; the gate also verified refusing unconfirmed and mis-named confirmations). Media generation requires the billing-enabled project described in Operating Rules.
