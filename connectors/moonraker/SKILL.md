---
name: "moonraker"
description: "Control a Klipper 3D printer through Moonraker: print jobs, file uploads, emergency stop, smart plugs, and gated raw G-code. Trigger phrases: moonraker, klipper, mainsail, fluidd, start print, pause print, emergency stop."
metadata: { "includeInPrompt": true }
tagline: "Control a Klipper-based 3D printer through the Moonraker API server (the backend behind Mainsail, Fluidd and RatOS): read server and print status, list and upload gcode files, start/pause/resume/cancel prints, trigger the emergency stop, toggle smart-plug devices, and (gated) run raw G-code. Use when the user mentions Moonraker, Klipper, Mainsail, or Fluidd."
catalog_auth: "no credential needed on most LAN installs (optional API key via the secure credential flow)"
catalog_hosts: ["the host you pass via --host"]
---

# Moonraker

## Purpose
Control a Klipper-based 3D printer through the Moonraker API server (the backend behind Mainsail, Fluidd and RatOS): read server and print status, list and upload gcode files, start/pause/resume/cancel prints, trigger the emergency stop, toggle smart-plug devices, and (gated) run raw G-code. Use when the user mentions Moonraker, Klipper, Mainsail, or Fluidd.

## Tooling
All commands go through `bin/moonraker.py`. `--host` points at Moonraker (default `$MOONRAKER_HOST` or `http://localhost:7125`); `--insecure` skips TLS verification for self-signed reverse proxies. `--api-key` attaches the stored `custom.moonraker` credential; omit it on the default no-auth LAN setup.

```bash
bin/moonraker.py auth --host http://printer.local:7125   # server info; never needs a credential
bin/moonraker.py status                                   # print state and temperatures
bin/moonraker.py files                                    # list gcode files

# MEDIUM: --confirm "<exact effect>" on first use per printer, then proceed
bin/moonraker.py upload --path ./benchy.gcode --confirm "upload benchy.gcode to printer.local"
bin/moonraker.py print-start --filename benchy.gcode --confirm "start printing benchy.gcode on printer.local"
bin/moonraker.py print-pause --confirm "pause the print on printer.local"
bin/moonraker.py print-resume --confirm "resume the print on printer.local"
bin/moonraker.py print-cancel --confirm "cancel the print on printer.local"
bin/moonraker.py emergency-stop \
    --confirm "emergency stop on printer.local: halt all motion and heaters"
bin/moonraker.py device-power --device enclosure --action on \
    --confirm "turn smart-plug device enclosure on on printer.local"

# HIGH: raw G-code needs BOTH --enable-raw-gcode AND --confirm on EVERY call
bin/moonraker.py gcode-script --script "G28" --enable-raw-gcode \
    --confirm "run raw G-code script: G28"
```

MEDIUM first-use confirmations are recorded locally (`~/.cache/muse-connectors/moonraker/confirmed.json`).

## Auth
- Provider id: `moonraker` (credential is collected as `custom.moonraker`)
- Collection: Moonraker has no auth on the LAN by default, so most installs need nothing stored at all. If the printer enables `[authorization]` API keys, store the key via the secure credential flow (`credentials.request_api_access`) as `custom.moonraker` and pass `--api-key` on each call. The key is never passed on the command line, in the environment, or in a file: `--api-key` is a flag that takes no value.
- Allowed hosts: the hostname from `--host` (validated per call; the surrogate is only ever swapped on egress to that host)
- Status check: `bin/moonraker.py auth` (must return `"ok": true`; also reports whether an API key is stored)
- Remote access: Moonraker is LAN-first. Reach it remotely through the OctoEverywhere relay, a VPN, or a reverse proxy; the connector does not implement any relay itself.

## Operating Rules
1. **HIGH: raw G-code (`gcode-script`) can physically damage the printer.** The CLI requires both `--enable-raw-gcode` (explicit capability flag) and `--confirm "run raw G-code script: <script>"` naming the exact script, on every call. Prefer the high-level print commands whenever they cover the need.
2. MEDIUM: print start/pause/resume/cancel, emergency stop, file upload, and smart-plug power move or heat physical hardware. They need `--confirm` naming the exact effect on first use per printer. Emergency stop halts all motion and heaters instantly; reach for it when a print is failing rather than using it as a casual pause.
3. There are no vendor quotas, but do not hammer the printer's host: keep status polling to a few times a minute at most.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit any key value.

## Files
- SKILL.md
- bin/moonraker.py

## Maturity
🧪 Draft: written from Moonraker's public API docs; not yet live-tested end-to-end.

Honesty flags: endpoint paths (`/server/info`, `/printer/objects/query`, `/server/files/list`, `/server/files/upload`, `/printer/print/{start,pause,resume,cancel}`, `/printer/emergency_stop`, `/printer/gcode/script`, `/machine/device_power/device`) follow the official Moonraker reference. Raw G-code is HIGH and doubly gated (`--enable-raw-gcode` plus per-call `--confirm`). The `[authorization]` API-key placement is configured in the credential store at collection time; if Moonraker expects the key somewhere other than the default header placement, reconfigure the credential rather than passing the key on the command line.
