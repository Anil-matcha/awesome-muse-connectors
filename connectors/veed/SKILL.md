---
name: "veed"
description: "Remove video backgrounds with VEED's direct developer API: standard, fast and green-screen endpoints. Trigger phrases: veed, remove video background, background removal, transparent video."
metadata: { "includeInPrompt": true }
tagline: "Remove backgrounds from video with VEED's direct developer API (POST /v1/video/background-remove): standard quality, fast throughput and green-screen chroma-key with spill suppression. Outputs are VP9-with-alpha or H.264 RGB+alpha, up to 4K."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["the host you pass via --api-host"]
---

# VEED

## Purpose
Remove backgrounds from video with VEED's direct developer API (`POST /v1/video/background-remove`): standard quality, fast throughput and green-screen chroma-key with spill suppression. Outputs are VP9-with-alpha or H.264 RGB+alpha, up to 4K.

VEED also serves lip-sync and talking-video models through fal.ai (`veed/lipsync`, `veed/fabric-1.0`); those are covered by the separate `fal-ai` connector.

## Tooling
All commands go through `bin/veed.py`. `--api-host` is required on every command (see Auth):

```bash
bin/veed.py auth --api-host https://<VEED_API_HOST>                      # check readiness (no free status endpoint)
bin/veed.py background-remove --api-host https://<VEED_API_HOST> \
    --file ./talking-head.mp4 --endpoint standard --output-format vp9_alpha  # confirm first: metered
bin/veed.py background-remove --api-host https://<VEED_API_HOST> \
    --file ./bulk.mp4 --endpoint fast --output-format h264_rgba --resolution 4k
bin/veed.py background-remove --api-host https://<VEED_API_HOST> \
    --file ./greenscreen.mp4 --endpoint green_screen --output-format vp9_alpha \
    --webhook-url "https://..."                                          # async completion for long jobs
```

The API returns a time-limited signed `output_url`; download the processed video promptly instead of storing the URL. Long jobs can run async with a webhook callback.

## Auth
- Provider id: `veed` (credential is collected as `custom.veed`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); VEED's developer docs describe how to obtain one
- Header: `Authorization: Bearer <API_KEY>` (the CLI builds this from the credential surrogate)
- Allowed hosts: the host you pass via `--api-host` (the credential is only ever sent there)
- Status check: `bin/veed.py auth --api-host <host>` (VEED has no free status endpoint, so this only confirms the credential is stored and the host is set)

**Open item (unresolved, never guessed):** VEED publishes the path `POST /v1/video/background-remove` but no base host in its public developer docs (veed.io/api currently routes new developers to fal.ai keys). The CLI refuses to run without an explicit `--api-host`; confirm the host from VEED's developer documentation or your VEED API dashboard before use.

## Operating Rules
1. **Confirm before every `background-remove`**: usage is metered per second/minute/frame with no subscription, so each call has a real cost. Name the file, the endpoint and the output format.
2. Bulk/batch processing multiplies the cost; confirm the batch size explicitly.
3. Never invent a base host. If VEED has not confirmed one, say so and stop.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/veed.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/veed.py

## Maturity
Draft: written from VEED's published API docs; not live-tested end-to-end, and the direct API base host is an unresolved open item (see Auth). The fal-hosted VEED models are intentionally out of scope here.
