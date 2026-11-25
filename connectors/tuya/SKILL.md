---
name: "tuya"
description: "Read and control Tuya / Smart Life devices: plugs, lights, thermostats, curtains, smart locks. Trigger phrases: tuya, smart life, tuya device, smart life plug."
metadata: { "includeInPrompt": true }
tagline: "Read status and send control commands to Tuya Cloud / Smart Life devices: smart plugs and switches, lights, thermostats, curtain motors, and supported smart locks, plus executing saved scenes. Use it when the user asks about or wants to change anything paired through the Tuya or Smart Life app. Commands drive real physical hardware, so writes are confirmation-gated (see Operating Rules)."
catalog_auth: "Access ID + Access Secret pair via the secure credential flow"
catalog_hosts: ["openapi.tuyaus.com", "openapi.tuyaeu.com", "openapi.tuyacn.com", "openapi.tuyain.com"]
---

# Tuya

## Purpose
Read status and send control commands to Tuya Cloud / Smart Life devices:
smart plugs and switches, lights, thermostats, curtain motors, and supported
smart locks, plus executing saved scenes. Use it when the user asks about or
wants to change anything paired through the Tuya or Smart Life app. Commands
drive real physical hardware, so writes are confirmation-gated (see Operating
Rules).

## Tooling
All commands go through `bin/tuya.py`. `--region` must match the account's
Tuya data-center region (`us`, `eu`, `cn`, `in`; default `us`):

```bash
bin/tuya.py auth --region us                          # status check: fetch a cloud token
bin/tuya.py device --id <device_id> --region us       # read device information
bin/tuya.py status --id <device_id> --region us       # read data-point status

# Writes. Smart-lock data points are HIGH: they REQUIRE --confirm naming the
# exact physical effect, on every run:
bin/tuya.py command --id <device_id> --code lock_motor_state --value true \
    --confirm "unlock the side door smart lock" --region us

# Other commands (relays, HVAC, curtains) are MEDIUM: --confirm on first use
# per device, then proceed:
bin/tuya.py command --id <device_id> --code switch_1 --value true \
    --confirm "turn on the workshop smart plug" --region us
bin/tuya.py command --id <device_id> --code temp_set --value 24 \
    --confirm "set the bedroom AC to 24 degrees" --region us

# Scenes are HIGH (their effects are whatever was saved into them):
bin/tuya.py scene --home <home_id> --scene <scene_id> \
    --confirm "run the Goodnight scene (locks doors, turns off lights)" --region us
```

`--value` is JSON-parsed: booleans (`true`), numbers (`24`), and quoted
strings (`'"off"'`); anything else falls back to a plain string. Find a
device's data-point codes with `device` (specification) and its current
values with `status`.

## Auth
- Provider id: `tuya` (credential is collected as `custom.tuya`)
- Collection: ONE combined value `access_id:access_secret` via the secure
  credential flow (`credentials.request_api_access`). Get both from a Tuya IoT
  Platform cloud project (Access ID + Access Secret); devices bind to the
  project via the Tuya / Smart Life app QR link. The CLI fetches a short-lived
  cloud token itself (`GET /v1.0/token?grant_type=1`) and signs every request
  with HMAC-SHA256 per Tuya's documented scheme.
- Allowed hosts: `openapi.tuyaus.com`, `openapi.tuyaeu.com`,
  `openapi.tuyacn.com`, `openapi.tuyain.com` (plus the `-ueaz`/`-weaz`
  variants)
- Status check: `bin/tuya.py auth --region <your region>`

## Operating Rules
1. **HIGH actuations are blocked without explicit confirmation.** Smart-lock
   data points (any `--code` containing `lock`) and scene executions require
   `--confirm "<exact physical effect>"` on every run. Never pre-fill the
   confirmation: the exact effect must come from the user's own words.
2. **MEDIUM actuations confirm on first use per device.** Relay toggles, HVAC
   mode and setpoints, curtain motors: `--confirm` the first time a device
   is actuated; the CLI records it locally
   (`~/.config/muse-connectors/tuya/confirmed.json`) and later runs proceed.
3. A scene's physical effects are whatever the user saved into it. Before
   confirming a scene execution, read back to the user what the scene does if
   it is not obvious from its name.
4. **Region must match the account region.** Calls against the wrong regional
   host return auth errors even with correct credentials; ask the user which
   region their Tuya project lives in (US, EU, China, India) instead of
   guessing repeatedly.
5. **Cost warning:** the Trial Edition is free up to about 26,000 API calls
   plus ~68,000 message subscriptions per month, extendable to 6 months;
   sustained or commercial use moves to paid editions. Poll `status` sparingly.
6. Reads (`auth`, `device`, `status`) never need confirmation.
7. **Open item:** the request signature is computed over the credential
   surrogate as delivered by the credential store. Confirm the signature
   verifies against Tuya's servers on first live use; if the runtime's
   egress handling breaks signed headers, this connector needs a signing
   adjustment before writes are trusted.
8. Never exfiltrate the credential: the CLI only ever handles surrogates. Do
   not print, log, or transmit the Access ID, Access Secret, or token values.

## Files
- SKILL.md
- bin/tuya.py

## Maturity
🧪 Draft: written from Tuya's public Cloud API docs; not yet live-tested
end-to-end. The HMAC-SHA256 signature construction, the token-grant flow,
and the scene-trigger path (`POST /v1.0/homes/{home_id}/scenes/{scene_id}/trigger`)
are untested against real Tuya servers.
