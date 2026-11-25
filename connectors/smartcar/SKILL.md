---
name: "smartcar"
description: "Read and control connected cars across brands through the Smartcar API: telemetry, lock/unlock, charge control, navigation. Trigger phrases: smartcar, connected car, lock my car, car charge, car location, odometer."
metadata: { "includeInPrompt": true }
tagline: "Read and control connected cars across many brands (Tesla, Ford, GM, Toyota, BMW, Hyundai and others) through one standardized API. Read odometer, location, charge and battery level, fuel level and tire pressure; lock/unlock doors; start/stop charging; set charge limits and schedules; route the built-in navigation. Use when the user mentions their car and the brand has no dedicated connector here, or asks for cross-brand vehicle telemetry and control."
catalog_auth: "provider OAuth 2.0 (Smartcar Connect) via the secure credential flow"
catalog_hosts: ["api.smartcar.com"]
---

# Smartcar

## Purpose
Read and control connected cars across many brands (Tesla, Ford, GM, Toyota, BMW, Hyundai and others) through one standardized API. Read odometer, location, charge and battery level, fuel level and tire pressure; lock/unlock doors; start/stop charging; set charge limits and schedules; route the built-in navigation. Use when the user mentions their car and the brand has no dedicated connector here, or asks for cross-brand vehicle telemetry and control.

## Tooling
All commands go through `bin/smartcar.py`. `--vehicle-id` is the Smartcar vehicle ID from `vehicles`.

```bash
bin/smartcar.py auth                                            # verify the OAuth token
bin/smartcar.py vehicles                                        # list connected vehicles
bin/smartcar.py telemetry --vehicle-id UUID --metric odometer   # odometer, location, charge, battery, fuel, tires

# HIGH: lock/unlock needs --confirm "<exact effect>" on EVERY call
bin/smartcar.py security --vehicle-id UUID --action LOCK --confirm "lock the vehicle doors"
bin/smartcar.py security --vehicle-id UUID --action UNLOCK --confirm "unlock the vehicle doors"

# MEDIUM: --confirm "<exact effect>" on first use per vehicle, then proceed
bin/smartcar.py charge --vehicle-id UUID --action START --confirm "start EV charging"
bin/smartcar.py charge --vehicle-id UUID --action STOP --confirm "stop EV charging"
bin/smartcar.py charge-limit --vehicle-id UUID --limit 80 --confirm "set the charge limit to 80%"

# LOW: no confirmation
bin/smartcar.py navigate --vehicle-id UUID --lat 37.33 --lon -121.89

# MEDIUM: charge schedules as a JSON object per the Smartcar docs
bin/smartcar.py charge-schedules --vehicle-id UUID \
    --schedules '{"schedules": [{"days": ["MONDAY"], "startTime": "22:00", "endTime": "06:00"}]}' \
    --confirm "replace the vehicle's charge schedules"
```

MEDIUM first-use confirmations are recorded locally (`~/.cache/muse-connectors/smartcar/confirmed.json`).

## Auth
- Provider id: `smartcar` (credential is collected as `custom.smartcar`)
- Collection: provider OAuth (Smartcar Connect) via the secure credential flow (`credentials.request_api_access`); same OAuth pattern as the `slack` and `x` connectors. Register the app at dashboard.smartcar.com to get the client ID and secret.
- Required scopes: granted at the Smartcar Connect consent step (read_vehicle_info, read_location, read_odometer, control_security, control_charge, etc., per what the commands need)
- Allowed hosts: `api.smartcar.com`
- Status check: `bin/smartcar.py auth` (must return `"ok": true`)
- Sandbox by default: build and test against a Smartcar app in test mode with simulated vehicles first; the CLI talks to `https://api.smartcar.com` in both modes, and switching a vehicle to a real car is a dashboard setting on the Smartcar app: flip the app from test mode to live mode. No CLI flag changes this.
- Cost warning: Smartcar bills per connected vehicle on paid plans; check current pricing at smartcar.com before connecting a fleet.

## Operating Rules
1. **HIGH: `security` LOCK/UNLOCK changes physical access to the car.** The CLI requires `--confirm` naming the exact effect on every call. No standing permission, no exceptions.
2. MEDIUM: `charge` START/STOP, `charge-limit`, and `charge-schedules` move a physical charge relay or change charging behavior. They need `--confirm` naming the exact effect on first use per vehicle; reads and `navigate` need no confirmation.
3. Per-brand capability differences are real: not every make supports every command (an ICE car has no charge endpoints; some brands lack remote unlock). If the API returns an incompatibility error, report it as a brand limitation rather than a bug.
4. Keep telemetry polling modest; location and odometer reads are the ones users ask to repeat.
5. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/smartcar.py

## Maturity
🧪 Draft: written from Smartcar's public API docs; not yet live-tested end-to-end.

Honesty flags: endpoint paths and payload shapes (`/v2.0/vehicles`, telemetry metrics, `security`, `charge`, `charge-limit`, `navigation/destination`, `charge-schedules`) are pinned in the official Smartcar API reference. Lock/unlock is HIGH and confirmation-gated on every call. The charge-schedules payload is model-dependent and untested here; validate the JSON against the Smartcar docs before first use on a real car.
