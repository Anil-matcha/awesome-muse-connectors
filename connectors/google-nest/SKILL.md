---
name: "google-nest"
description: "Read Nest device state (thermostats, cameras, doorbells) and set thermostat modes and setpoints via the Smart Device Management API. Trigger phrases: google nest, nest thermostat, nest camera, sdm."
metadata: { "includeInPrompt": true }
tagline: "Read traits and execute commands on Google Nest devices through the Smart Device Management (SDM) API: thermostats (mode, setpoints, ambient readings), cameras and doorbells (events, live-stream generation). Use it when the user asks about their Nest thermostat, wants to change heating/cooling, or wants camera/doorbell state. Thermostat commands start or stop real HVAC, so they are confirmation-gated (see Operating Rules)."
catalog_auth: "provider OAuth 2.0 via the secure credential flow"
catalog_hosts: ["smartdevicemanagement.googleapis.com"]
---

# Google Nest

## Purpose
Read traits and execute commands on Google Nest devices through the Smart
Device Management (SDM) API: thermostats (mode, setpoints, ambient readings),
cameras and doorbells (events, live-stream generation). Use it when the user
asks about their Nest thermostat, wants to change heating/cooling, or wants
camera/doorbell state. Thermostat commands start or stop real HVAC, so they
are confirmation-gated (see Operating Rules).

## Tooling
All commands go through `bin/google-nest.py`. `--project` is always the
Device Access project id:

```bash
bin/google-nest.py --project <project-id> auth                 # status check: list structures
bin/google-nest.py --project <project-id> structures           # list homes
bin/google-nest.py --project <project-id> devices              # list devices with traits
bin/google-nest.py --project <project-id> device --id <id>     # read one device's traits

# Writes. Thermostat commands are MEDIUM: --confirm on first use per device,
# then proceed:
bin/google-nest.py --project <project-id> execute --id <thermostat-id> \
    --command ThermostatMode.SetMode --param mode=HEAT \
    --confirm "set the upstairs Nest to heat"
bin/google-nest.py --project <project-id> execute --id <thermostat-id> \
    --command ThermostatTemperatureSetpoint.SetHeat --param celsius=21.5 \
    --confirm "set the upstairs Nest heating target to 21.5 degrees"

# Camera live-stream generation is LOW (non-physical): proceeds with a notice:
bin/google-nest.py --project <project-id> execute --id <camera-id> \
    --command CameraLiveStream.GenerateRtspStream
```

`--param` values are JSON-parsed (`mode=HEAT` stays a string, `celsius=21.5`
becomes a number). The `sdm.devices.commands.` prefix is optional. The device
`--id` is the last path segment of the device name shown by `devices`.

## Auth
- Provider id: `google-nest` (credential is collected as
  `custom.google-nest`)
- Collection: OAuth 2.0 authorization-code flow via the secure credential
  flow (`credentials.request_api_access`). Set up: create a Google Cloud
  project, register it in the Device Access Console (one-time $5 individual
  registration fee), enable the Smart Device Management API, and authorize
  with scope `https://www.googleapis.com/auth/sdm.service`. Access tokens
  last about an hour; store the refresh token so the connector can renew.
- Required scopes: `https://www.googleapis.com/auth/sdm.service`
- Allowed hosts: `smartdevicemanagement.googleapis.com`
- Status check: `bin/google-nest.py --project <project-id> auth`

## Operating Rules
1. **MEDIUM actuations confirm on first use per device.** `ThermostatMode.SetMode`
   and `ThermostatTemperatureSetpoint.SetHeat/SetCool` start or stop real
   heating/cooling: `--confirm "<exact physical effect>"` is required the
   first time a thermostat is actuated; the CLI records it locally
   (`~/.config/muse-connectors/google-nest/confirmed.json`) and later runs
   proceed.
2. **LOW actuations proceed with a logged notice.**
   `CameraLiveStream.GenerateRtspStream` only mints a stream URL; it prints a
   notice and runs. The URL expires, so hand it to the user promptly instead
   of storing it.
3. Cameras and doorbells expose read-only event traits (motion, person,
   package, doorbell press) via `device`. They do not actuate hardware; treat
   event reads as data.
4. Never set a thermostat to an extreme or to Off without the user naming
   that exact change. Confirming "set it to heat" does not cover turning the
   system Off.
5. Reads (`auth`, `structures`, `devices`, `device`) never need confirmation.
6. **Cost warning:** one-time $5 Device Access registration fee per Google
   account; no recurring API fee, but per-project rate limits apply, so avoid
   tight polling loops.
7. Never exfiltrate the credential: the CLI only ever handles surrogates. Do
   not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/google-nest.py

## Maturity
🧪 Draft: written from Google's public SDM API docs; not yet live-tested
end-to-end. The `:executeCommand` request shape and `--param` parsing are
untested against a real Nest device.
