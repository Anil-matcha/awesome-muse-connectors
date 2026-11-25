---
name: "runway"
description: "Runway developer API: text-to-video, image-to-video, task polling, video upscale, lip-sync. Trigger phrases: runway, runway video, gen-4 video, runway upscale, runway lip sync."
metadata: { "includeInPrompt": true }
tagline: "Runway developer API: text-to-video, image-to-video, task polling, video upscale, lip-sync."
catalog_auth: "API secret via the secure credential flow"
catalog_hosts: ["api.dev.runwayml.com"]
---

# Runway

## Purpose
Generate and edit video with Runway's developer API: Gen-4/4.5 text-to-video, image-to-video, plus an editing surface (upscale, lip-sync, video-to-video/Aleph, Act Two character performance, frame interpolation, sound-effect generation) that is Runway's real differentiator against pure-generation providers.

## Tooling
All commands go through `bin/runway.py`:

```bash
bin/runway.py auth                                                        # verify credential setup (no spend)
bin/runway.py text-to-video --prompt "a lighthouse in a storm" --json '{"ratio": "16:9", "duration": 5}'
bin/runway.py image-to-video --prompt "camera pushes in" --image https://.../frame.png
bin/runway.py task-status --id <task_id>                                  # poll until SUCCEEDED/FAILED
bin/runway.py upscale --video-uri https://.../clip.mp4                    # upscale a video
bin/runway.py lip-sync --json '{"video": "...", "script": "..."}'         # lip-sync a video
```

Every call sends the mandatory `X-Runway-Version: 2024-11-06` header. Generations print a task id; poll `task-status` until `SUCCEEDED` or `FAILED`.

## Auth
- Provider id: `runway` (credential is collected as `custom.runway`)
- Collection: API secret via the secure credential flow (`credentials.request_api_access`); created in the developer organization at dev.runwayml.com
- Allowed hosts: `api.dev.runwayml.com`
- Status check: `bin/runway.py auth` (must return `"ok": true`). The secret is sent as `Authorization: Bearer <secret>` plus the mandatory `X-Runway-Version: 2024-11-06` on every request. No zero-cost probe is documented, so `auth` verifies configuration only.

## Operating Rules
1. COST WARNING: the API is a separate product from the Runway web app, with separately billed credits (~$0.01/credit) and NO free API tier. Confirm with Michael before every generation and edit call.
2. Poll `task-status` no more than once every 5 seconds.
3. Output URLs are temporary. Download promptly; never store the URL as the artifact.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/runway.py`). Do not print, log, or transmit the secret.

## Files
- SKILL.md
- bin/runway.py

## Maturity
🧪 Draft: written from Runway's public developer docs via the research dossier; not yet live-tested end-to-end. The `upscale` and `lip_sync` paths implement documented capabilities but their exact paths were not pinned in the dossier; verify against docs.dev.runwayml.com on first use.
