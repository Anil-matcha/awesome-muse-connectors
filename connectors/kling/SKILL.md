---
name: "kling"
description: "Kling AI video generation with client-side JWT auth: text-to-video, image-to-video, status polling, clip extend, lip-sync. Trigger phrases: kling, kling video, klingai, kling text to video."
metadata: { "includeInPrompt": true }
tagline: "Kling AI video generation with client-side JWT auth: text-to-video, image-to-video, status polling, clip extend, lip-sync."
catalog_auth: "access key + secret key pair via the secure credential flow"
catalog_hosts: ["api.klingai.com"]
---

# Kling

## Purpose
Generate top-tier video with Kling's official open platform: text-to-video, image-to-video, clip extension, and lip-sync, plus Kolors image generation and talking-avatar endpoints on the same platform. Use when Michael wants the highest-quality AI video clips. Kling is also reachable through fal.ai with simpler auth (trade-off: fal's markup).

## Tooling
All commands go through `bin/kling.py`:

```bash
bin/kling.py auth                                                         # mint a JWT and verify it is accepted (free)
bin/kling.py text2video --prompt "a samurai in neon rain" --json '{"duration": "10"}'
bin/kling.py image2video --image-url https://.../frame.png --prompt "slow zoom out"
bin/kling.py status --task-id <task_id>                                   # poll until succeed/failed
bin/kling.py extend --task-id <task_id> --json '{"prompt": "continue forward"}'   # extend a finished clip
bin/kling.py lip-sync --json '{"voice_id": "...", "video": "..."}'       # lip-sync a video
```

`text2video` and `image2video` print a `task_id`. Poll `status` with backoff until the task succeeds, then download the asset immediately. `--json` merges extra fields (duration, aspect_ratio, model_name) into the request.

## Auth
- Provider id: `kling` (credential is collected as `custom.kling`)
- Collection: access key + secret key pair via the secure credential flow (`credentials.request_api_access`); created at app.klingai.com/global/dev. Stored as ONE value in `access_key:secret_key` format.
- Allowed hosts: `api.klingai.com`
- Status check: `bin/kling.py auth` (must return `"ok": true`). Auth is unusual: the CLI splits the credential on the first colon, mints a short-lived HS256 JWT per request with stdlib hmac (iss = access key, exp ~30 min), and sends `Authorization: Bearer <jwt>`. The secret never leaves the vault path.

## Operating Rules
1. Kling uses prepaid resource packs. Confirm with Michael before every `text2video`, `image2video`, `extend`, and `lip-sync`; failed tasks are reportedly not charged.
2. Generated asset URLs are short-lived. Download immediately; never store the URL as the artifact.
3. JWT minting is handled entirely inside `bin/kling.py`. Never mint or print tokens elsewhere, and never log the secret.
4. Model IDs move through v2.6/3.0 lineage. Confirm the current model id in Kling's docs before pinning one.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/kling.py`). Do not print, log, or transmit the key pair.

## Files
- SKILL.md
- bin/kling.py

## Maturity
🧪 Draft: written from Kling's public developer docs via the research dossier; not yet live-tested end-to-end. JWT minting logic needs a live check on first use.
