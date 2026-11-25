---
name: "homey"
description: "Read and control devices on a Homey Pro hub or Homey cloud account: lights, thermostats, locks, blinds, Flows. Trigger phrases: homey, homey pro, homey flow, athom."
metadata: { "includeInPrompt": true }
tagline: "Read device state and write capability values on a Homey Pro (local) or Homey cloud account through the Homey Web API: lights and outlets, dimmers and color, thermostats, connected locks, blinds and curtains, plus listing Flows (automations). Use it when the user asks about or wants to change anything paired to their Homey. Writes drive real physical hardware, so they are confirmation-gated (see Operating Rules)."
catalog_auth: "personal API token or OAuth via the secure credential flow"
catalog_hosts: ["the host you pass via --host"]
---

# Homey

## Purpose
Read device state and write capability values on a Homey Pro (local) or Homey
cloud account through the Homey Web API: lights and outlets, dimmers and
color, thermostats, connected locks, blinds and curtains, plus listing Flows
(automations). Use it when the user asks about or wants to change anything
paired to their Homey. Writes drive real physical hardware, so they are
confirmation-gated (see Operating Rules).

## Tooling
All commands go through `bin/homey.py`. `--host` is required on every run:
the API root, either local (`http://<homey-ip>/api`) or cloud
(`https://<cloud-id>.connect.athom.com/api`):

```bash
bin/homey.py --host http://192.168.1.60/api auth               # status check: verify token, count devices
bin/homey.py --host <api-root> devices                          # list devices with capabilities
bin/homey.py --host <api-root> device --id <id>                 # device detail

# Writes. Lock writes are HIGH: they REQUIRE --confirm naming the exact
# physical effect, on every run:
bin/homey.py --host <api-root> set --id <id> --cap locked --value false \
    --confirm "unlock the side door"

# Other capability writes are MEDIUM: --confirm on first use per device, then
# proceed:
bin/homey.py --host <api-root> set --id <id> --cap onoff --value true \
    --confirm "turn on the living room floor lamp"
bin/homey.py --host <api-root> set --id <id> --cap target_temperature --value 21 \
    --confirm "set the bedroom thermostat target to 21 degrees"

# Blind/curtain writes are LOW: they proceed with a logged notice:
bin/homey.py --host <api-root> set --id <id> --cap windowcoverings_state --value up

# Flows:
bin/homey.py --host <api-root> flows
bin/homey.py --host <api-root> flow-trigger --id <flow-id> \
    --confirm "run the Good Morning flow (opens blinds, starts coffee machine)"
```

`--value` is JSON-parsed: `true`, `0.5`, `21`, `'"heat"'`. Capability names
follow Homey's conventions: `onoff`, `dim`, `locked`, `target_temperature`,
`thermostat_mode`, `windowcoverings_state`, `light_hue`, `light_saturation`.

**Open item:** `flow-trigger` ships with an UNTESTED path
(`POST /manager/flow/flow/{id}/trigger`). Its exact form could not be pinned
from public docs at build time; verify it against Athom's docs on first live
use. It is HIGH-gated regardless.

## Auth
- Provider id: `homey` (credential is collected as `custom.homey`)
- Collection: personal API token (Homey Pro) or OAuth 2.0 token (Homey cloud)
  via the secure credential flow (`credentials.request_api_access`). The CLI
  sends it as `Authorization: Bearer <token>`.
- Allowed hosts: whatever `--host` names (the Homey's LAN IP/hostname or
  `<cloud-id>.connect.athom.com`). The CLI pins egress to that host per run.
- Status check: `bin/homey.py --host <api-root> auth`

## Operating Rules
1. **HIGH actuations are blocked without explicit confirmation.** Setting
   `locked` to false (unlock) or true (lock) requires
   `--confirm "<exact physical effect>"` on every run. Triggering a Flow is
   also HIGH: a Flow's physical effects are whatever its actions do, so
   `--confirm` must name them, and the Flow's actions should be read back to
   the user before confirming when they are not obvious.
2. **MEDIUM actuations confirm on first use per device.** `onoff`, `dim`,
   `light_hue`/`light_saturation`, thermostat capabilities: `--confirm` the
   first time a device is actuated; the CLI records it locally
   (`~/.config/muse-connectors/homey/confirmed.json`) and later runs proceed.
3. **LOW actuations proceed with a logged notice.** `windowcoverings_state`
   and `windowcoverings_set` (blinds/curtains) print a notice to stderr and
   run without confirmation.
4. **Never lock someone out or in.** Do not set `locked` to true unless the
   user explicitly asked for that lock to be locked; verify intent in
   conversation first.
5. Reads (`auth`, `devices`, `device`, `flows`) never need confirmation.
6. Homey Pro hardware or a Homey cloud account is required; local calls stay
   on the LAN.
7. Never exfiltrate the credential: the CLI only ever handles surrogates. Do
   not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/homey.py

## Maturity
🧪 Draft: written from Homey's public Web API docs; not yet live-tested
end-to-end. Device capability reads and PUTs are pinned; the Flow-trigger
path is an open item and ships marked untested.
