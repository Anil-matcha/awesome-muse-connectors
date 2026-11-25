---
name: "hubitat"
description: "Read and control devices on a Hubitat Elevation hub via the Maker API: lights, locks, thermostats, garage doors, HSM. Trigger phrases: hubitat, maker api, hubitat lock, hubitat hub."
metadata: { "includeInPrompt": true }
tagline: "Read device states and invoke capability commands on a Hubitat Elevation hub through the official Maker API app: lights and dimmers, deadbolt locks, garage door controllers, thermostats, location modes, and the Hubitat Safety Monitor (HSM). Use it when the user asks about or wants to change anything paired to their Hubitat hub. Commands drive real physical hardware, so writes are confirmation-gated (see Operating Rules)."
catalog_auth: "Maker API token via the secure credential flow"
catalog_hosts: ["the host you pass via --host"]
---

# Hubitat

## Purpose
Read device states and invoke capability commands on a Hubitat Elevation hub
through the official Maker API app: lights and dimmers, deadbolt locks,
garage door controllers, thermostats, location modes, and the Hubitat Safety
Monitor (HSM). Use it when the user asks about or wants to change anything
paired to their Hubitat hub. Commands drive real physical hardware, so writes
are confirmation-gated (see Operating Rules).

## Tooling
All commands go through `bin/hubitat.py`. `--host` is required on every run:
the local Maker API base URL (`http://<hub-ip>/apps/api/<app-id>`) or the
cloud relay URL the Maker API app issues:

```bash
bin/hubitat.py --host http://192.168.1.50/apps/api/12 auth        # status check: verify token, count devices
bin/hubitat.py --host <base> devices                               # list devices with current attributes
bin/hubitat.py --host <base> device --id <id>                      # device detail
bin/hubitat.py --host <base> events --id <id>                      # recent device events

# Writes. lock/unlock and garage open/close are HIGH: they REQUIRE --confirm
# naming the exact physical effect, on every run:
bin/hubitat.py --host <base> command --id <id> --command unlock \
    --confirm "unlock the front door deadbolt"
bin/hubitat.py --host <base> command --id <id> --command close \
    --confirm "close the garage door"

# Lights, dimmers, thermostats are MEDIUM: --confirm on first use per device,
# then proceed:
bin/hubitat.py --host <base> command --id <id> --command on \
    --confirm "turn on the kitchen lights"
bin/hubitat.py --host <base> command --id <id> --command setLevel --param 30 \
    --confirm "dim the hallway lights to 30 percent"
bin/hubitat.py --host <base> command --id <id> --command setHeatingSetpoint --param 68 \
    --confirm "set the thermostat heating target to 68"

# Modes and HSM are MEDIUM (first use needs --confirm):
bin/hubitat.py --host <base> modes
bin/hubitat.py --host <base> mode-set --id <mode-id> --confirm "set house mode to Away"
bin/hubitat.py --host <base> hsm
bin/hubitat.py --host <base> hsm-set --state armAway \
    --confirm "arm the Hubitat Safety Monitor in Away mode"
```

`--param` values become extra path segments in order (`setLevel` takes the
level; `setHeatingSetpoint` takes the degrees). Device command names follow
the device's capabilities: `on`, `off`, `setLevel`, `lock`, `unlock`,
`open`, `close`, `setThermostatMode`, `setCoolingSetpoint`, and so on.

## Auth
- Provider id: `hubitat` (credential is collected as `custom.hubitat`)
- Collection: Maker API access token via the secure credential flow
  (`credentials.request_api_access`). On the hub: Apps > Maker API, enable
  the devices Muse may touch, and copy the access token shown for the app
  instance. The CLI appends it as `?access_token=<token>` on every request.
  Note that the token travels in the query string: prefer the local LAN URL
  over the cloud relay when possible, and treat the token like a password.
- Allowed hosts: whatever `--host` names (local hub IP/hostname or the cloud
  relay host). The CLI pins egress to that host per run.
- Status check: `bin/hubitat.py --host <base> auth`

## Operating Rules
1. **HIGH actuations are blocked without explicit confirmation.** `lock`,
   `unlock`, `open`, and `close` (deadbolts, garage doors) require
   `--confirm "<exact physical effect>"` on every run. Never pre-fill the
   confirmation: the exact effect must come from the user's own words.
2. **MEDIUM actuations confirm on first use per device.** Lights, dimmers,
   thermostat commands, location-mode changes, and HSM arm/disarm need
   `--confirm` the first time; the CLI records it locally
   (`~/.config/muse-connectors/hubitat/confirmed.json`) and later runs
   proceed. Arming HSM enables intrusion/smoke/water monitoring and
   siren/strobe alerts: say so when confirming.
3. **Never lock someone out or in.** Do not lock a door unless the user
   explicitly asked for that lock to be locked; verify intent in conversation
   before the first lock command on any device.
4. Reads (`auth`, `devices`, `device`, `events`, `modes`, `hsm`) never need
   confirmation.
5. The Maker API only exposes devices the user enabled in the app. If a
   device is missing, enable it in the hub's Maker API settings first.
6. Local calls stay on the LAN with no cloud dependency; the cloud relay URL
   works remotely but routes the token through Hubitat's cloud.
7. Never exfiltrate the credential: the CLI only ever handles surrogates. Do
   not print, log, or transmit the token value (and remember it travels in
   the query string, so never paste a full request URL anywhere).

## Files
- SKILL.md
- bin/hubitat.py

## Maturity
🧪 Draft: written from Hubitat's public Maker API docs; not yet live-tested
end-to-end. The command path-segment form and the HSM/mode endpoints are
untested against a real hub.
