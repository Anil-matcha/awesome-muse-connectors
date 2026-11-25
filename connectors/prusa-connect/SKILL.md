---
name: "prusa-connect"
description: "Read Prusa Connect cloud state for Prusa 3D printers: printers, jobs, files, cameras, stats, plus file upload. Trigger phrases: prusa connect, prusa printer, prusa job, prusa camera."
metadata: { "includeInPrompt": true }
tagline: "Read Prusa 3D printer state through the official Prusa Connect cloud API: list printers and their state, list jobs and files, view cameras, read print statistics, and upload gcode files to printer storage. Use when the user mentions Prusa Connect or a networked Prusa printer (MK3/MK4/CORE One)."
catalog_auth: "personal API token via the secure credential flow"
catalog_hosts: ["connect.prusa3d.com"]
---

# Prusa Connect

## Purpose
Read Prusa 3D printer state through the official Prusa Connect cloud API: list printers and their state, list jobs and files, view cameras, read print statistics, and upload gcode files to printer storage. Use when the user mentions Prusa Connect or a networked Prusa printer (MK3/MK4/CORE One).

## Tooling
All commands go through `bin/prusa-connect.py`.

```bash
bin/prusa-connect.py auth          # verify the API token
bin/prusa-connect.py printers      # printers and their state
bin/prusa-connect.py jobs          # jobs and their status
bin/prusa-connect.py files         # files in printer storage
bin/prusa-connect.py files --printer-id 12345
bin/prusa-connect.py cameras       # printer cameras
bin/prusa-connect.py stats         # print statistics

# MEDIUM, untested payload: --confirm "<exact effect>" on first use per printer
bin/prusa-connect.py upload --path ./benchy.gcode \
    --confirm "upload benchy.gcode to Prusa Connect printer storage"
```

Job pause/resume/cancel/restart are deliberately not shipped (see Maturity): the CLI will not guess their paths.

## Auth
- Provider id: `prusa-connect` (credential is collected as `custom.prusa-connect`)
- Collection: personal API token ("Access token") created in the Prusa Connect web UI under Settings > API Access, stored via the secure credential flow (`credentials.request_api_access`); sent as `Authorization: Bearer <token>`
- Allowed hosts: `connect.prusa3d.com`
- Status check: `bin/prusa-connect.py auth` (must return `"ok": true`)

## Operating Rules
1. Reads (`auth`, `printers`, `jobs`, `files`, `cameras`, `stats`) need no confirmation.
2. `upload` is a MEDIUM actuation (it writes to printer storage): it needs `--confirm` naming the exact effect on first use per printer. The upload payload is untested in this build, so verify the file landed in the Prusa Connect web UI before starting a print from it.
3. Job pause/resume/cancel/restart are not available in this CLI. Do not improvise paths for them; the open item below explains why.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/prusa-connect.py

## Maturity
🧪 Draft: written from the Prusa Connect API surface; not yet live-tested end-to-end.

Honesty flags: the read paths (`/api/printers`, `/api/jobs`, `/api/files`, `/api/cameras`, `/api/stats`) and the `POST /api/files` upload path are pinned in the documented API surface, but the exact write-endpoint paths for job pause/resume/cancel/restart could not be pinned from the official docs or the community SDK mirror at build time (2026-09-16), so they are deliberately not shipped. The `upload` payload shape is a standard multipart form and is untested; verify uploads in the web UI. This connector never guesses paths: anything unpinned stays out until it can be verified.
