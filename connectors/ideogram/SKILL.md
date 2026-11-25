---
name: "ideogram"
description: "Ideogram text-to-image generation with the strongest text rendering in the catalog: generate, edit, remix, upscale, describe, balance. Trigger phrases: ideogram, text in image, thumbnail with words, ideogram generate, magic fill."
metadata: { "includeInPrompt": true }
tagline: "Ideogram text-to-image generation with the strongest text rendering in the catalog: generate, edit, remix, upscale, describe, balance."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.ideogram.ai"]
---

# Ideogram

## Purpose
Generate images with Ideogram's v3 API: the strongest option in the catalog for text-in-image rendering (thumbnails and carousels with real words), plus Magic Fill editing and style remix, with upscaling and image description on the same key. Use when Michael needs images that contain legible text.

## Tooling
All commands go through `bin/ideogram.py` (multipart form posts):

```bash
bin/ideogram.py auth                                                      # verify the API key (free balance read)
bin/ideogram.py balance                                                   # read billing balance (free)
bin/ideogram.py generate --prompt "retro poster that says SUMMER" --json '{"aspect_ratio": "16x9"}'
bin/ideogram.py edit --prompt "replace the sign with OPEN" --image ./sign.png     # Magic Fill edit
bin/ideogram.py remix --prompt "same scene, watercolor style" --image ./scene.png # style transfer
bin/ideogram.py upscale --image ./small.png                               # upscale
bin/ideogram.py describe --image ./photo.png                              # describe an image
```

`generate` returns image URLs in the response. Ideogram is SYNCHRONOUS (no job polling), which makes it the simplest image integration in the catalog.

## Auth
- Provider id: `ideogram` (credential is collected as `custom.ideogram`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in the Ideogram developer dashboard
- Allowed hosts: `api.ideogram.ai`
- Status check: `bin/ideogram.py auth` (must return `"ok": true`). The key is sent as the `Api-Key` header. HEADER NOTE: the research dossier documented "header auth" without naming the header; `Api-Key` is per Ideogram's published API docs. Verify against developer.ideogram.ai on first live use and correct `bin/ideogram.py` if it differs.

## Operating Rules
1. Every generation/edit/remix/upscale spends balance (~$0.05-0.08/image by model/speed tier). Confirm with Michael before each one.
2. COST WARNING: Ideogram billing auto-tops-up: it refills to $20 when the balance drops below $10 (configurable). Read `balance` first so top-ups never surprise anyone.
3. Image URLs expire. Download immediately after generation; never store the URL as the artifact.
4. Default rate limit is 10 in-flight requests. Do not fan out more than that.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/ideogram.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/ideogram.py

## Maturity
🧪 Draft: written from Ideogram's published OpenAPI 3.1 spec via the research dossier; not yet live-tested end-to-end. The `Api-Key` header name and the `/api/v1/billing` path need a live check on first use.
