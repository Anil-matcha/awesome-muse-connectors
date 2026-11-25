---
name: "luma"
description: "Luma Dream Machine video generation: text-to-video and image-to-video, status polling, cancel, image upload. Trigger phrases: luma, dream machine, luma video, ray video."
metadata: { "includeInPrompt": true }
tagline: "Luma Dream Machine video generation: text-to-video and image-to-video, status polling, cancel, image upload."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.lumalabs.ai"]
---

# Luma (Dream Machine API)

## Purpose
Generate short-form video with Luma's Dream Machine API: text-to-video and image-to-video, plus generation cancel and image upload for reference frames. A strong default for short clips in the catalog. Confirm exact model IDs in docs.lumalabs.ai before use; the API surface skews toward Dream Machine generation.

## Tooling
All commands go through `bin/luma.py`:

```bash
bin/luma.py auth                                                          # verify the API key (free)
bin/luma.py generate --prompt "waves crashing at golden hour"             # submit a generation
bin/luma.py generate --prompt "slow push in" --image-url https://.../frame.png   # image-to-video
bin/luma.py generate --prompt "..." --model ray2 --json '{"aspect_ratio": "16:9"}'
bin/luma.py status --id <generation_id>                                   # poll (no faster than every 5s)
bin/luma.py cancel --id <generation_id>                                   # cancel a queued/running generation
bin/luma.py upload --file ./frame.png                                     # upload an image for reference frames
```

`generate` prints the generation id. Poll `status` with backoff; states move toward `completed` or `failed`. Webhooks are supported for production use.

## Auth
- Provider id: `luma` (credential is collected as `custom.luma`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in the Luma developer dashboard
- Allowed hosts: `api.lumalabs.ai`
- Status check: `bin/luma.py auth` (must return `"ok": true`). The key is sent as `Authorization: Bearer <key>`.

## Operating Rules
1. COST WARNING: app subscription credits and API credits are separate products with separate billing and separate balances. Do not mix them. Generations here spend API credits (~$0.08/sec for Ray2-class video; recheck the live pricing page).
2. Confirm with Michael before every `generate`, stating the model and expected duration/cost.
3. Poll `status` no faster than every ~5 seconds.
4. Output MP4 URLs are temporary. Download promptly; never store the URL as the artifact.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/luma.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/luma.py

## Maturity
🧪 Draft: written from Luma's public API docs via the research dossier; not yet live-tested end-to-end. The `/upload` path and current model IDs need a live check against docs.lumalabs.ai on first use.
