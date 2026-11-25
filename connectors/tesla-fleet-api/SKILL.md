---
name: "tesla-fleet-api"
description: "Control Tesla vehicles through the official Tesla Fleet API: lock/unlock, remote start, charge control, preconditioning, honk, trunk. Trigger phrases: tesla car, tesla vehicle, lock my tesla, precondition tesla, tesla charge."
metadata: { "includeInPrompt": true }
tagline: "Control Tesla vehicles through the official Tesla Fleet API: read live vehicle state, wake a sleeping car, and send signed commands (lock/unlock, keyless drive, charge control, preconditioning, honk/flash, trunk, sentry/valet, speed limit, navigation). Use when the user mentions their Tesla car or asks for vehicle actuation."
catalog_auth: "provider OAuth 2.0 via the secure credential flow"
catalog_hosts: ["fleet-api.prd.na.vn.cloud.tesla.com", "fleet-api.prd.eu.vn.cloud.tesla.com", "fleet-api.prd.cn.vn.cloud.tesla.com"]
---

# Tesla Fleet API (vehicles)

## Purpose
Control Tesla vehicles through the official Tesla Fleet API: read live vehicle state, wake a sleeping car, and send signed commands (lock/unlock, keyless drive, charge control, preconditioning, honk/flash, trunk, sentry/valet, speed limit, navigation). Use when the user mentions their Tesla car or asks for vehicle actuation.

This connector covers vehicles only and is fully separate from `tesla-powerwall` (energy devices): separate credential, separate scope set, separate CLI.

## Tooling
All commands go through `bin/tesla-fleet-api.py`. `--region` selects the API region (`na`, `eu`, `cn`; default `na`). `--vehicle` is the vehicle tag, usually the VIN.

```bash
bin/tesla-fleet-api.py auth                                       # verify the OAuth token
bin/tesla-fleet-api.py vehicles                                   # list vehicles
bin/tesla-fleet-api.py vehicle-data --vehicle YOUR_VIN              # live state (charge, location, climate, doors)
bin/tesla-fleet-api.py vehicle-data --vehicle YOUR_VIN --endpoints charge_state
bin/tesla-fleet-api.py wake --vehicle YOUR_VIN                      # wake a sleeping car (metered)

# HIGH actuations: --confirm "<exact effect>" required on EVERY call
bin/tesla-fleet-api.py command --vehicle YOUR_VIN --action door_lock \
    --confirm "lock all vehicle doors"
bin/tesla-fleet-api.py command --vehicle YOUR_VIN --action door_unlock \
    --confirm "unlock all vehicle doors"
bin/tesla-fleet-api.py command --vehicle YOUR_VIN --action remote_start_drive \
    --confirm "enable keyless driving for 2 minutes"

# MEDIUM actuations: --confirm "<exact effect>" on first use per vehicle, then proceed
bin/tesla-fleet-api.py command --vehicle YOUR_VIN --action charge_start \
    --confirm "start EV charging"
bin/tesla-fleet-api.py command --vehicle YOUR_VIN --action set_charge_limit \
    --params '{"percent": 80}' --confirm "change the charge limit"

# LOW actuations: no confirmation
bin/tesla-fleet-api.py command --vehicle YOUR_VIN --action honk_horn
bin/tesla-fleet-api.py command --vehicle YOUR_VIN --action auto_conditioning_start
bin/tesla-fleet-api.py command --vehicle YOUR_VIN --action actuate_trunk --params '{"which_trunk": "rear"}'
```

Available actions: `door_lock`, `door_unlock`, `remote_start_drive`, `charge_start`, `charge_stop`, `set_charge_limit`, `honk_horn`, `flash_lights`, `auto_conditioning_start`, `auto_conditioning_stop`, `actuate_trunk`, `set_sentry_mode`, `set_valet_mode`, `speed_limit_activate`, `speed_limit_set_limit`, `navigation_gps_request`, `schedule_software_update`. Extra command parameters go in `--params` as a JSON object.

MEDIUM first-use confirmations are recorded locally (`~/.cache/muse-connectors/tesla-fleet-api/confirmed.json`); HIGH actions always ask.

## Auth
- Provider id: `tesla-fleet-api` (credential is collected as `custom.tesla-fleet-api`)
- Collection: provider OAuth (OAuth 2.0 third-party tokens) via the secure credential flow (`credentials.request_api_access`); same OAuth pattern as the `slack` and `x` connectors
- Required scopes: `openid`, `offline_access`, `vehicle_device_data`, `vehicle_cmds`, `vehicle_charging_cmds`, `vehicle_location`
- Allowed hosts: `fleet-api.prd.na.vn.cloud.tesla.com`, `fleet-api.prd.eu.vn.cloud.tesla.com`, `fleet-api.prd.cn.vn.cloud.tesla.com` (selected with `--region`)
- Status check: `bin/tesla-fleet-api.py auth` (must return `"ok": true`)
- Signed commands need two things beyond the token: the developer app's public key hosted on a verified domain, and the vehicle paired to the app's virtual key. Without pairing, commands are rejected by the car.
- Onboarding burden: heaviest of this batch. Developer app approval needs legal business details, verified domain ownership, and a hosted public key, plus per-vehicle virtual-key pairing. Say so up front.

## Operating Rules
1. **HIGH actuations need explicit confirmation every time, naming the exact physical effect**: `door_lock` / `door_unlock` change physical access to the car; `remote_start_drive` opens a 2-minute window where the car can be driven without a key. The CLI refuses to run without the exact `--confirm` text. No standing permission, no exceptions.
2. MEDIUM actuations (charge start/stop/limit, sentry/valet mode, speed limit) need `--confirm` naming the exact effect on first use per vehicle; reads and LOW actuations (honk, flash, trunk, preconditioning, navigation destination, software-update scheduling) need no confirmation.
3. **Cost warning: Tesla bills pay-per-use.** Roughly $1 per 1,000 commands, $1 per 500 data requests, $1 per 50 wakes; a $10/month credit covers light individual use. `wake` and frequent `vehicle-data` polling spend real money: poll sparingly and say the cost when the user asks for repeated checks.
4. `vehicle-data` without `--endpoints` pulls the full state; pass `--endpoints` (semicolon-separated, e.g. `charge_state;climate_state`) to keep responses small and cheaper.
5. The `signed_command` envelope in the CLI follows the official Fleet API reference and is untested in this build. If the car rejects a command with a pairing error, the fix is virtual-key pairing; retrying will not help.
6. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/tesla-fleet-api.py

## Maturity
🧪 Draft: written from Tesla's public Fleet API docs; not yet live-tested end-to-end.

Honesty flags: the `vehicles`, `vehicle_data`, `wake_up`, and `signed_command` paths are pinned in the official docs. The signed-command request envelope (`routineName` plus action parameters) follows the official reference but has not been exercised here, and signed commands cannot work at all until the app's public key is hosted and the vehicle pairs the virtual key. `remote_start_drive` and lock/unlock are HIGH and confirmation-gated in the CLI on every call.
