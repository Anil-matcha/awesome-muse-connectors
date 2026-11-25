---
name: "smartthings"
description: "Read status and drive Samsung SmartThings devices — locations, rooms, modes, scenes, health, history, virtual switches — with confirmation-gated actuation. Trigger phrases: smartthings, samsung smart home, unlock the door, smartthings thermostat."
metadata: { "includeInPrompt": true }
tagline: "Read status and drive Samsung SmartThings: locations, rooms, devices, modes, scenes, health, history, virtual switches, MQTT discovery. Confirmation-gated actuation, hardened in code (exact-effect confirm for locks/doors; bound, expiring confirmations for medium-risk writes)."
catalog_auth: "provider OAuth 2.0 via the secure credential flow"
catalog_hosts: ["api.smartthings.com"]
---

# SmartThings

## Purpose
Read device status and issue capability commands across a Samsung SmartThings account: locations, rooms, devices (switches, dimmers, locks, thermostats, sirens, garage door controllers, window shades, sensors), location modes, scenes, device health, device-event history, cloud virtual switches, and MQTT broker discovery. Use it when the user asks about or wants to change the state of anything paired to their SmartThings hub or cloud account. This connector drives real physical hardware, so writes are confirmation-gated in the CLI itself (see Operating Rules).

Source: SmartThings API documentation (developer.smartthings.com), checked 2026-10-19. This version supersedes the earlier Draft catalog entry: the full CLI surface, health/history/MQTT commands, MCP-first route, and durable OAuth-refresh design come from a production deployment, and the actuation gating merges that entry's risk grading with hardened confirmation binding.

## Tooling
All commands go through `bin/smartthings.py`:

```bash
bin/smartthings.py auth                                    # status check: list locations
bin/smartthings.py locations                               # list locations
bin/smartthings.py rooms <locationId>                      # list rooms
bin/smartthings.py devices                                 # list devices (id, label, type)
bin/smartthings.py device <deviceId>                       # full device payload
bin/smartthings.py status <deviceId>                       # live capability states
bin/smartthings.py health <deviceId>                       # ONLINE / OFFLINE
bin/smartthings.py history [locationId] [--device <deviceId>] [--limit N]   # device-event history
bin/smartthings.py modes <locationId>                      # list location modes
bin/smartthings.py mode-current <locationId>               # current location mode
bin/smartthings.py mqtt-broker [locationId]                # MQTT broker URL for a location
bin/smartthings.py scenes                                  # list scenes

# Writes — confirmation-gated (see Operating Rules):
bin/smartthings.py command <deviceId> lock unlock --confirm "lock:unlock:<deviceId>"
bin/smartthings.py command <deviceId> switchLevel setLevel --arg 80 --confirm "dim the light to 80 percent"
bin/smartthings.py command <deviceId> switch on '[...]'    # args via [args-json] OR repeatable --arg, never both
bin/smartthings.py scene <sceneId> --confirm "run the goodnight scene"
bin/smartthings.py mode-set <locationId> <modeId|name> --confirm "set home mode to Night"
bin/smartthings.py vswitch <name> <roomId> [locationId] --confirm "create virtual switch Porch"
bin/smartthings.py delete <deviceId> --confirm "delete device <deviceId>"
```

`--component` defaults to `main`. Where a locationId is optional it defaults to the account's first location. Sensor reads come straight from `status` (for example illuminance in lux at `components.main.illuminanceMeasurement.illuminance.value`, motion at `components.main.motionSensor.motion.value` — always check the value's timestamp: motion is a recency signal, not true occupancy).

**Route note (production design):** for high-frequency agent reads, the production deployment this comes from prefers the SmartThings MCP server (veonua/smartthings-mcp) for device list/status/commands/history and uses this CLI for what the MCP lacks — location modes, scenes, virtual-switch creation, health, and full-fidelity payloads. Either route talks to the same API with the same credential; the gating rules below apply to this CLI.

## Auth
- Provider id: `smartthings` (credential is collected as `custom.smartthings`)
- Collection: OAuth 2.0 authorization-code flow via the secure credential flow (`credentials.request_api_access`). Set up: create an app at developer.smartthings.com with the scopes the user needs, complete the authorization-code grant, and store the resulting tokens. Personal Access Tokens now expire after about 24 hours, so a persistent connector must use the OAuth flow, not a PAT.
- Required scopes: `r:devices:*` at minimum for reads; add `x:devices:*` (commands) only for the devices the user wants Muse to actuate. Location/mode/scene operations need their matching `r:`/`x:` scopes (`locations`, `modes`, `scenes`).
- Allowed hosts: `api.smartthings.com`
- Status check: `bin/smartthings.py auth`

**Durable OAuth refresh (production design):** the token manager keeps the access + refresh tokens in a local store and refreshes proactively (5 minutes before expiry): POST to `https://api.smartthings.com/v1/oauth/token` with `grant_type=refresh_token`, authenticating with HTTP Basic client credentials (`client_secret_basic` — SmartThings rejects client credentials sent in the POST body against this endpoint). Refresh tokens rotate: persist the new refresh token from every response, write the store atomically (temp file + rename), and after any re-authorization force one live refresh cycle and confirm it persists before calling the setup done — "authorized" is not "durable".

## Operating Rules
1. **HIGH actuations are blocked without exact confirmation, every run.** The `lock` capability (any command) and `doorControl`/`garageDoorControl` `open`/`close` refuse to run unless `--confirm` exactly equals `<capability>:<command>:<deviceId>`. Never pre-fill the confirmation on the user's behalf: the user must confirm the exact physical effect in conversation first. Confirmations for HIGH are never remembered.
2. **MEDIUM actuations confirm on first use, bound and expiring.** All other device commands, scene execution, mode-set, virtual-switch creation, and device deletion need `--confirm "<exact effect>"` the first time; the CLI records the confirmation bound to the exact target (device + component + capability + command, or scene/mode/vswitch/delete target) **and a hash of the arguments**, with a 30-day expiry. Different arguments — a different thermostat setpoint, say — need a fresh confirmation; an expired record does too. (The earlier Draft entry remembered confirmations keyed only by device + capability with no arguments and no expiry; that could silently waive a materially different later command, so this version binds tighter.)
3. **LOW actuations** (window shade / curtain moves) proceed with a notice printed to stderr.
4. **Never lock someone out or in.** Do not lock a door unless the user explicitly asked for that lock to be locked; verify intent twice in conversation first.
5. Reads (`auth`, `locations`, `rooms`, `devices`, `device`, `status`, `health`, `history`, `modes`, `mode-current`, `mqtt-broker`, `scenes` list) never need confirmation.
6. Rate limit: roughly 120 requests/min on the commands endpoint per device/principal. Space out bulk actuations.
7. Samsung has announced paid SmartThings tiers (from about $4.99/month for the personal tier). Heavy or always-on use may fall under a paid tier.
8. Zigbee/Z-Wave devices need a SmartThings hub online; cloud-only devices work without one. Virtual switches created here are CLOUD execution (the create call is `POST /virtualdevices/prototypes` with prototype `VIRTUAL_SWITCH`; the `/virtualdevices` path 422s).
9. Rules (IF/THEN automations) are managed in the SmartThings Advanced web app (my.smartthings.com/advanced); the Rules REST API may return 403 depending on token scopes — don't treat that as an auth failure of this connector.
10. A 401/403 is a question about the request before it is a question about the credential — confirm the surrogate was attached and the scopes cover the operation. Never print, log, or persist raw tokens; the CLI only ever handles surrogates.

## Files
- SKILL.md
- bin/smartthings.py

## Maturity
✅ Live — this is the production version from a running Muse setup: the CLI and its MCP companion route run a real smart home daily (device reads, mode sync, scene execution, multisensor presence/lux reads, device health and history verified against the live API on 2026-10-19), and the actuation gate is enforced in code, not just documented.
