---
name: "elai"
description: "Elai AI avatar videos: list avatars, check videos, and render avatar videos. Trigger phrases: elai, avatar video, AI presenter, talking head video."
metadata: { "includeInPrompt": true }
tagline: "Build AI avatar presenter videos with Elai: list available avatars, inspect videos and their render status, submit renders, and poll until a render finishes. Reach for this when the user wants a talking-head video generated from a script or slide deck."
catalog_auth: "API token via the secure credential flow"
catalog_hosts: ["apis.elai.io"]
---

# Elai

## Purpose
Build AI avatar presenter videos with Elai: list available avatars, inspect videos and their render status, submit renders, and poll until a render finishes. Reach for this when the user wants a talking-head video generated from a script or slide deck.

## Tooling
All commands go through `bin/elai.py`.

```bash
bin/elai.py auth
# {"ok": true, "avatars": 40} on success

bin/elai.py avatars
# list available avatars (code, name, gender)

bin/elai.py videos
# list your videos (id, name, status)

bin/elai.py video-get --id <VIDEO_ID>
# one video: name, status; rendered video URL when ready

bin/elai.py render --id <VIDEO_ID>
# submit a render for a drafted video; consumes render credits (confirmation-gated)

bin/elai.py render-status --id <VIDEO_ID>
# poll render status; prints status and the video URL when the render completes
```

Notes:
- Rendering is asynchronous: `render` submits the job, then poll `render-status` until `status` leaves `rendering`. Download the resulting video promptly; do not treat the URL as a permanent artifact.
- Custom-avatar footage submission (the PATCH-based workflow) and WebRTC real-time streaming are outside CLI scope.

## Auth
- Provider id: `elai` (credential is collected as `custom.elai`)
- Collection: Elai API token via the secure credential flow (`credentials.request_api_access`); only the account primary (admin) user can generate one, under Settings, then API Keys
- Allowed hosts: `apis.elai.io`
- Connect placement: `bearer_header` (the token goes in `Authorization: Bearer <token>`)
- Status check: `bin/elai.py auth`

## Operating Rules
1. **Video renders consume credits and are confirmation-gated**: confirm the exact video id with the user before running `render`. Poll `render-status` after submitting.
2. **Custom-avatar submissions are confirmation-gated**: confirm with the user before submitting custom-avatar footage (training a likeness).
3. Slide layouts are complex. The recommended flow is: build the layout in the Elai UI, fetch it with `video-get`, and use that structure as the base for API-created videos.
4. Never log or print the raw token; the CLI only ever handles the surrogate.

## Files
- SKILL.md
- bin/elai.py

## Maturity
🧪 Draft: written from Elai's public API reference with the host, auth header and render paths verified at build time; not yet live-tested end-to-end. Story API, personalization and the custom-avatar PATCH workflow are not yet in the CLI.
