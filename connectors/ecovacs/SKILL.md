---
name: "ecovacs"
description: "Control Ecovacs DEEBOT robot vacuums through the Ecovacs Open Platform: device list, status, battery, cleaning start/pause/stop, dock return. Trigger phrases: ecovacs, deebot, robot vacuum, start cleaning, dock vacuum."
metadata: { "includeInPrompt": true }
tagline: "Control Ecovacs DEEBOT robot vacuums through the official Ecovacs Open Platform: list bound robots, read robot state and battery, start/pause/resume/stop cleaning, send the robot back to its dock, and set the sweep/mop work mode. Use when the user mentions their DEEBOT or robot vacuum."
catalog_auth: "Access Key via the secure credential flow"
catalog_hosts: ["open.ecovacs.com", "open.ecovacs.cn"]
---

# Ecovacs

## Purpose
Control Ecovacs DEEBOT robot vacuums through the official Ecovacs Open Platform: list bound robots, read robot state and battery, start/pause/resume/stop cleaning, send the robot back to its dock, and set the sweep/mop work mode. Use when the user mentions their DEEBOT or robot vacuum.

## Tooling
All commands go through `bin/ecovacs.py`. `--region` selects the Open Platform region (`global` for open.ecovacs.com, `cn` for open.ecovacs.cn; default `global`) and must match the region of the user's Ecovacs account and robots. `--robot` is the robot's nickname (a fragment of the name shown in the app is enough for the gateway to match it).

```bash
bin/ecovacs.py auth --region global                 # verify the Access Key
bin/ecovacs.py devices                              # list bound robots
bin/ecovacs.py status --robot Blue                  # cleaning/paused/docked state
bin/ecovacs.py battery --robot Blue                 # battery percent
bin/ecovacs.py stats --robot Blue                   # area cleaned, duration

# MEDIUM: cleaning start needs --confirm "<exact effect>" on first use per robot
bin/ecovacs.py clean --robot Blue --confirm "start cleaning on Blue"

# LOW: no confirmation
bin/ecovacs.py pause --robot Blue
bin/ecovacs.py resume --robot Blue
bin/ecovacs.py stop --robot Blue
bin/ecovacs.py dock --robot Blue
bin/ecovacs.py undock --robot Blue
bin/ecovacs.py set-work-mode --robot Blue --mode 0  # 0=sweep+mop, 1=sweep only, 2=mop only, 3=sweep then mop
```

The `clean` command starts a whole-home clean. Zone/room cleaning needs area IDs from the map and is not shipped; use the app for targeted cleans.

## Auth
- Provider id: `ecovacs` (credential is collected as `custom.ecovacs`)
- Collection: self-serve Access Key (AK) created or viewed in the Ecovacs Open Platform console under Service overview, stored via the secure credential flow (`credentials.request_api_access`) with query-param placement on `ak`. The AK is passed as `?ak=` on the request URL, per Ecovacs' vendor-published Deebot skill reference; it never appears on the command line, in the environment, or in a file.
- Allowed hosts: `open.ecovacs.com`, `open.ecovacs.cn` (selected with `--region`)
- Status check: `bin/ecovacs.py auth` (must return `"ok": true`)
- Region matters: use the same regional portal for the AK, the account, and the robots, or calls fail with AK/permission errors. This is the most common setup mistake.

## Operating Rules
1. `clean` (start cleaning) is a MEDIUM actuation: the robot drives itself around the home. It needs `--confirm "start cleaning on <robot>"` naming the exact robot on first use per robot; the CLI records it locally (`~/.cache/muse-connectors/ecovacs/confirmed.json`) and later runs proceed without asking.
2. Pause, resume, stop, dock return, and work-mode changes are LOW: they are trivially reversible and need no confirmation, but the assistant should still say what it is about to do in chat for dock/undock.
3. Discovery and control use the documented gateway paths only (`/robot/skill/deviceList`, `/robot/skill/ctl` with CloudCtl commands `Clean`, `Charge`, `GetWorkState`, `GetBatteryInfo`, `GetStats`, `SetWorkMode`). Control requests carry the AK as `?ak=` on the request URL; the vendor reference also documents it in the JSON body, so if the gateway rejects the query placement, confirm the placement against the Open Platform docs rather than changing the code.
4. What actually works depends on model, firmware and whether the robot is online. A `ret=fail` with `errno=5009` means the command or casing is not supported on that model; `10000` means low battery; `10004` means offline.
5. Pricing and quotas were unpublished at build time; check the Open Platform console for current terms.
6. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the AK value.

## Files
- SKILL.md
- bin/ecovacs.py

## Maturity
🧪 Draft: written from Ecovacs' Open Platform materials and the vendor-published Deebot skill reference; not yet live-tested end-to-end.

Honesty flags: the gateway paths and the CloudCtl command/data shapes (`Clean` with `act` s/p/r/h, `Charge` with `act` go/stopGo, `GetWorkState`, `GetBatteryInfo`, `GetStats`, `SetWorkMode`) are pinned in the vendor-published skill reference (2026-09-16), but no live call has been made from this CLI. The AK-as-query-param placement on `POST /robot/skill/ctl` follows the documented `GET` semantics; if the gateway requires the AK in the JSON body for control calls, adjust the credential placement at setup instead of changing the code.
