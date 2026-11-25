---
name: "rachio"
description: "Control a Rachio smart sprinkler controller: check schedules, start watering zones, and stop all water. Trigger phrases: rachio, sprinklers, irrigation controller, water the lawn, stop watering."
metadata: { "includeInPrompt": true }
tagline: "Control a Rachio smart irrigation controller through the public Rachio API. Check who is signed in, see what the controller is currently running, start watering a specific zone for a set number of seconds, and shut all water off in an emergency. Reach for this when the user asks about sprinklers, watering schedules, or irrigation zones."
catalog_auth: "personal API key via the secure credential flow"
catalog_hosts: ["api.rach.io"]
---

# Rachio

## Purpose
Control a Rachio smart irrigation controller through the public Rachio API. Check who is signed in, see what the controller is currently running, start watering a specific zone for a set number of seconds, and shut all water off in an emergency. Reach for this when the user asks about sprinklers, watering schedules, or irrigation zones.

## Tooling
All commands go through `bin/rachio.py`:

```bash
bin/rachio.py auth                                        # verify the API key
bin/rachio.py person                                      # person info + controller ids
bin/rachio.py schedule --device-id DEVICE_ID              # current schedule on a controller
bin/rachio.py zone-start --zone-id ZONE_ID --seconds 600 \
    --confirm "water zone ZONE_ID for 600 seconds"        # open a zone valve (water flows)
bin/rachio.py stop                                        # EMERGENCY OFF: closes all valves
bin/rachio.py device-on --device-id DEVICE_ID \
    --confirm "enable controller DEVICE_ID"               # enable a controller
bin/rachio.py device-off --device-id DEVICE_ID \
    --confirm "disable controller DEVICE_ID"              # disable a controller
```

Zone ids come from the Rachio app or a prior `person` call. `stop` never asks for confirmation: it is the emergency off and closes every open valve immediately.

## Auth
- Provider id: `rachio` (credential is collected as `custom.rachio`)
- Collection: personal API key via the secure credential flow (`credentials.request_api_access`); generate one in the Rachio app under Account settings
- Auth scheme: `Authorization: Bearer <token>` on every request
- Allowed hosts: `api.rach.io`
- Status check: `bin/rachio.py auth`

## Operating Rules
1. **`zone-start` opens a real valve and water flows.** It requires `--confirm` with the exact string the CLI echoes (e.g. `water zone <id> for <seconds> seconds`). The string must match exactly; a missing or wrong confirmation refuses the call. This is stricter than the standing medium-risk rule: confirmation is required for every start, with no first-use shortcut per device.
2. `device-on` / `device-off` also require the echoed `--confirm` string every time.
3. `stop` (close all valves) needs no confirmation: it only ever shuts water off.
4. The Rachio API is free and rate-limited to roughly 1,700 requests per day. Space out polling; do not loop `schedule` on a short interval.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/rachio.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/rachio.py

## Maturity
Draft: written from Rachio's public API docs; not yet live-tested end-to-end.
