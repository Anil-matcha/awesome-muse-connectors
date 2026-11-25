---
name: "octoprint"
description: "Control an OctoPrint 3D printer over its local REST API: print jobs, temperatures, file uploads, and gated raw G-code. Trigger phrases: octoprint, 3d printer, start print, pause print, nozzle temperature, bed temperature, gcode."
metadata: { "includeInPrompt": true }
tagline: "Control an OctoPrint 3D printer over its local REST API: read printer state and temperatures, monitor print progress, start/pause/cancel/restart jobs, upload and select gcode files, set hotend and bed temperatures, jog or home axes, and (gated) run raw G-code. Use when the user mentions their OctoPrint instance or a printer it drives."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["the host you pass via --host"]
---

# OctoPrint

## Purpose
Control an OctoPrint 3D printer over its local REST API: read printer state and temperatures, monitor print progress, start/pause/cancel/restart jobs, upload and select gcode files, set hotend and bed temperatures, jog or home axes, and (gated) run raw G-code. Use when the user mentions their OctoPrint instance or a printer it drives.

## Tooling
All commands go through `bin/octoprint.py`. `--host` points at the OctoPrint instance (default `$OCTOPRINT_HOST` or `http://localhost:5000`); `--insecure` skips TLS verification for self-signed reverse proxies.

```bash
bin/octoprint.py auth --host http://octopi.local:5000     # verify the API key
bin/octoprint.py version                                   # server version
bin/octoprint.py status                                    # printer state, hotend and bed temps
bin/octoprint.py job                                       # current print progress
bin/octoprint.py files                                     # list gcode files on the printer
bin/octoprint.py printhead --command home --x-home --y-home --z-home   # home axes (LOW)

# MEDIUM: --confirm "<exact effect>" on first use per printer, then proceed
bin/octoprint.py job-cmd --command start --confirm "start the print job on octopi.local"
bin/octoprint.py job-cmd --command pause --confirm "pause the print job on octopi.local"
bin/octoprint.py job-cmd --command cancel --confirm "cancel the print job on octopi.local"
bin/octoprint.py upload --path ./benchy.gcode --confirm "upload benchy.gcode to octopi.local"
bin/octoprint.py file-select --path benchy.gcode \
    --confirm "select file benchy.gcode for printing on octopi.local"
bin/octoprint.py tool-temp --tool tool0 --temp 210 \
    --confirm "heat tool0 to 210C on octopi.local (physical heater)"
bin/octoprint.py bed-temp --temp 60 \
    --confirm "heat the print bed to 60C on octopi.local (physical heater)"

# HIGH: raw G-code needs BOTH --enable-raw-gcode AND --confirm on EVERY call
bin/octoprint.py gcode --command "G28" --enable-raw-gcode --confirm "run raw G-code: G28"
```

`job-cmd --command start` starts the currently selected file; run `file-select` first if nothing is loaded. MEDIUM first-use confirmations are recorded locally (`~/.cache/muse-connectors/octoprint/confirmed.json`).

## Auth
- Provider id: `octoprint` (credential is collected as `custom.octoprint`)
- Collection: API key generated in OctoPrint under Settings > Application Keys (or the global API key), stored via the secure credential flow (`credentials.request_api_access`); sent as the `X-Api-Key` request header
- Allowed hosts: the hostname from `--host` (validated per call; the surrogate is only ever swapped on egress to that host)
- Status check: `bin/octoprint.py auth` (must return `"ok": true`)
- Remote access: OctoPrint is LAN-first. Reach it remotely through the OctoEverywhere free-tier relay, a VPN, or a reverse proxy; the connector does not implement any relay itself.

## Operating Rules
1. **HIGH: raw G-code (`gcode`) can physically damage the printer.** The CLI requires both `--enable-raw-gcode` (explicit capability flag) and `--confirm "run raw G-code: <command>"` naming the exact command, on every call. Prefer the high-level commands (`job-cmd`, `tool-temp`, `bed-temp`, `printhead`) whenever they cover the need; reach for raw G-code only when nothing else does.
2. MEDIUM: job start/pause/cancel/restart, file upload/select, and heater targets move or heat physical hardware. They need `--confirm` naming the exact effect on first use per printer. Heating a hotend or bed unattended is fire-adjacent: say so when confirming, and never set temperatures while the user is away without their explicit say-so.
3. `connection disconnect` mid-print cancels the print; the CLI warns but proceeds (LOW).
4. There are no vendor quotas, but do not hammer a Raspberry Pi running OctoPrint: keep status polling to a few times a minute at most.
5. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the API key value.

## Files
- SKILL.md
- bin/octoprint.py

## Maturity
🧪 Draft: written from OctoPrint's public REST API docs; not yet live-tested end-to-end.

Honesty flags: endpoint paths and payload shapes (`/api/job`, `/api/files`, `/api/printer/tool`, `/api/printer/bed`, `/api/printer/printhead`, `/api/printer/command`, `/api/connection`) follow the official OctoPrint REST reference. Raw G-code is HIGH and doubly gated (`--enable-raw-gcode` plus per-call `--confirm`). The multipart upload body is standard form encoding but untested against a live OctoPrint here.
