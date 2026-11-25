---
name: "aqara"
description: "Read and control Aqara smart home devices: plugs, switches, lights, AC, locks, curtains, scenes. Trigger phrases: aqara, aqara hub, aqara lock, aqara curtain."
metadata: { "includeInPrompt": true }
tagline: "Read device attributes and send control commands to Aqara devices through the Aqara Open Cloud API: plugs and wall switches, lights (brightness, color temperature), air conditioners, supported locks, curtain motors, and saved scenes, organized by homes and rooms. Use it when the user asks about or wants to change anything in their Aqara setup. Zigbee devices need an Aqara hub online. Commands drive real physical hardware, so writes are confirmation-gated (see Operating Rules)."
catalog_auth: "OAuth-style account authorization via the secure credential flow"
catalog_hosts: ["open-<region>.aqara.com"]
---

# Aqara

## Purpose
Read device attributes and send control commands to Aqara devices through the
Aqara Open Cloud API: plugs and wall switches, lights (brightness, color
temperature), air conditioners, supported locks, curtain motors, and saved
scenes, organized by homes and rooms. Use it when the user asks about or wants
to change anything in their Aqara setup. Zigbee devices need an Aqara hub
online. Commands drive real physical hardware, so writes are
confirmation-gated (see Operating Rules).

## Tooling
All commands go through `bin/aqara.py`. `--region` picks the regional host
(`open-<region>.aqara.com`, e.g. `us`, `eu`, `cn`; default `us`).

**Every path below is UNTESTED.** The exact REST path form and the request
signature headers could not be pinned from public docs at build time (see
Operating Rules, open items). Verify every command against the official
OpenAPI reference on first live use before trusting it.

```bash
bin/aqara.py auth --region us                         # UNTESTED: status check, list homes
bin/aqara.py homes --region us                        # UNTESTED: list homes
bin/aqara.py rooms --home <home_id> --region us       # UNTESTED: list rooms
bin/aqara.py devices --home <home_id> --region us     # UNTESTED: list devices
bin/aqara.py status --device <device_id> --region us  # UNTESTED: read device attributes

# Writes (all UNTESTED paths). Lock endpoints are HIGH: --confirm on every run:
bin/aqara.py control --device <device_id> --action on --attribute lock \
    --confirm "unlock the front door Aqara lock" --region us

# Plug/switch toggles and AC changes are MEDIUM: --confirm on first use per
# device, then proceed:
bin/aqara.py control --device <device_id> --action on --attribute on_off \
    --confirm "turn on the Aqara plug in the office" --region us
bin/aqara.py control --device <device_id> --action set --attribute ac_mode \
    --value '"cool"' --confirm "set the bedroom AC to cool" --region us

# Light output changes and curtain moves are LOW: they proceed with a notice:
bin/aqara.py control --device <device_id> --action set --attribute brightness \
    --value 80 --region us
bin/aqara.py control --device <device_id> --action up --attribute curtain \
    --region us

# Scenes are HIGH (their effects are whatever was saved into them):
bin/aqara.py scenes --home <home_id> --region us
bin/aqara.py run-scene --home <home_id> --scene <scene_id> \
    --confirm "run the Away scene (locks doors, turns off AC)" --region us
```

`--value` is JSON-parsed (`80` becomes a number, `'"cool"'` a string).
`--endpoint` defaults to `1`; pass comma-separated ids for multi-gang
devices.

## Auth
- Provider id: `aqara` (credential is collected as `custom.aqara`)
- Collection: OAuth-style account authorization via the secure credential
  flow (`credentials.request_api_access`). Complete the authorization flow at
  developer.aqara.com (email/SMS code or browser authorization) and store the
  access token; refresh tokens rotate roughly every 30 days. The CLI sends
  the token as `Authorization: Bearer <token>`.
- Allowed hosts: `open-<region>.aqara.com` (region-dependent, e.g.
  `open-us.aqara.com`)
- Status check: `bin/aqara.py auth --region <your region>`

## Operating Rules
1. **Open item: paths and signature are unverified.** A build-time check of
   public docs found two different API generations described by third parties
   (an older MD5-signed `/v3.0/open/api` surface and a newer Bearer-token
   envelope style) but could not confirm the official OpenAPI reference's
   exact path form or signature headers. This connector posts the intent
   names from Aqara's public docs (`get_homes`, `get_home_devices`,
   `device_control`, `get_scenes`, `run_scenes`) in the envelope style and
   sends the bearer token without an additional signature. Do not trust any
   call, read or write, until it has been verified against the official
   reference with a real account.
2. **HIGH actuations are blocked without explicit confirmation.** Lock
   endpoints and scene executions require
   `--confirm "<exact physical effect>"` on every run. Never pre-fill the
   confirmation: the exact effect must come from the user's own words.
3. **MEDIUM actuations confirm on first use per device.** Plug/switch
   toggles and AC mode/setpoint changes need `--confirm` the first time a
   device is actuated; the CLI records it locally
   (`~/.config/muse-connectors/aqara/confirmed.json`) and later runs proceed.
4. **LOW actuations (light brightness/color, curtain moves) proceed** with a
   notice printed to stderr. No confirmation needed.
5. A scene's physical effects are whatever the user saved into it. Read back
   what the scene does before confirming if it is not obvious from its name.
6. Zigbee devices require an Aqara hub online and bound to the account.
7. Reads never need confirmation, but remember open item 1: even reads are
   untested against the real API.
8. Never exfiltrate the credential: the CLI only ever handles surrogates. Do
   not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/aqara.py

## Maturity
🧪 Draft: written from Aqara's public developer docs and third-party
references; not yet live-tested end-to-end, and the request path form plus
the signature headers are unresolved open items. Treat every command as a
candidate to repoint at connect time.
