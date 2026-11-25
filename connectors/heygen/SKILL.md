---
name: "heygen"
description: "HeyGen avatar and talking-head video: prompt-to-video agent, multi-scene avatar video, status polling, avatar and voice lists. Trigger phrases: heygen, avatar video, talking head video, video agent."
metadata: { "includeInPrompt": true }
tagline: "HeyGen avatar and talking-head video: prompt-to-video agent, multi-scene avatar video, status polling, avatar and voice lists."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.heygen.com"]
---

# HeyGen

## Purpose
Generate talking-head and avatar videos with HeyGen's self-serve API: one-shot prompt-to-video via the Video Agent, or multi-scene avatar videos assembled from stock or custom avatars and voices. The best self-serve avatar-video path in the catalog; translation/dubbing endpoints also exist. Use when Michael wants presenter-style or explainer videos.

## Tooling
All commands go through `bin/heygen.py`:

```bash
bin/heygen.py auth                                                        # verify the API key (free)
bin/heygen.py avatars --limit 25                                          # list stock avatars (custom avatar IDs come from the app)
bin/heygen.py voices --limit 25                                           # list voices
bin/heygen.py video-agent --prompt "Explain compounding in 30 seconds"    # one-shot prompt-to-video
bin/heygen.py video-generate --json '{"avatar_id": "...", "voice_id": "...", "script": "..."}'   # multi-scene
bin/heygen.py video-status --video-id <video_id>                           # poll until completed
```

`video-agent` takes a plain prompt. `video-generate` needs the full multi-scene spec as `--json` (avatar_id, voice_id, script or scenes, per HeyGen's docs). Both print a `video_id`; poll `video-status` until completed, then download the MP4.

## Auth
- Provider id: `heygen` (credential is collected as `custom.heygen`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created at app.heygen.com/api
- Allowed hosts: `api.heygen.com`
- Status check: `bin/heygen.py auth` (must return `"ok": true`). The key is sent verbatim as the `X-Api-Key` header.

## Operating Rules
1. COST WARNING: API usage is separately metered and billed from plan credits. Do not assume the plan quota applies; generations here spend API balance.
2. Confirm with Michael before every `video-agent` and `video-generate` call. Renders take 2-5 minutes; poll with backoff.
3. Custom avatars cost $99 one-time with a 24-48h turnaround. Order them in the HeyGen app; the API cannot create them. Confirm before ordering one.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/heygen.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/heygen.py

## Maturity
🧪 Draft: written from HeyGen's public API docs via the research dossier; not yet live-tested end-to-end.
