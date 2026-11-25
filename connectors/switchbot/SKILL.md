---
name: "switchbot"
description: "Read and control SwitchBot devices: Bots, Locks, curtains, plugs, lights, AC, IR remotes, scenes. Trigger phrases: switchbot, switchbot lock, switchbot bot, switchbot curtain."
metadata: { "includeInPrompt": true }
tagline: "Read status and send commands to SwitchBot devices over the official OpenAPI v1.1: SwitchBot Bot (physical button presser), SwitchBot Lock, Curtain and Blind Tilt motors, plugs, lights, air conditioners, infrared remotes, and saved scenes. Use it when the user asks about or wants to change anything in their SwitchBot setup. Commands drive real physical hardware, so writes are confirmation-gated (see Operating Rules)."
catalog_auth: "token + secret pair via the secure credential flow"
catalog_hosts: ["api.switch-bot.com"]
---

# SwitchBot

## Purpose
Read status and send commands to SwitchBot devices over the official OpenAPI
v1.1: SwitchBot Bot (physical button presser), SwitchBot Lock, Curtain and
Blind Tilt motors, plugs, lights, air conditioners, infrared remotes, and
saved scenes. Use it when the user asks about or wants to change anything in
their SwitchBot setup. Commands drive real physical hardware, so writes are
confirmation-gated (see Operating Rules).

## Tooling
All commands go through `bin/switchbot.py`:

```bash
bin/switchbot.py auth                                   # status check: verify token, count devices
bin/switchbot.py devices                                # list devices and IR remotes
bin/switchbot.py status --id <deviceId>                 # read device status

# Writes. lock/unlock are HIGH: they REQUIRE --confirm naming the exact
# physical effect, on every run:
bin/switchbot.py command --id <deviceId> --command lock \
    --confirm "lock the back door SwitchBot lock"
bin/switchbot.py command --id <deviceId> --command unlock \
    --confirm "unlock the back door SwitchBot lock"

# press / turnOn / turnOff / setAll are MEDIUM: --confirm on first use per
# device, then proceed:
bin/switchbot.py command --id <deviceId> --command press \
    --confirm "press the coffee machine power button with the SwitchBot Bot"
bin/switchbot.py command --id <deviceId> --command turnOn \
    --confirm "turn on the SwitchBot plug in the workshop"
bin/switchbot.py command --id <deviceId> --command setAll \
    --param mode=1 --param temperature=24 --param fanSpeed=2 \
    --confirm "set the bedroom AC to cool 24 degrees, fan medium"

# Curtain/blind moves (setPosition) are LOW: they proceed with a logged notice:
bin/switchbot.py command --id <deviceId> --command setPosition --param position=0

# Scenes are HIGH (their effects are whatever was saved into them):
bin/switchbot.py scenes
bin/switchbot.py scene-execute --scene-id <sceneId> \
    --confirm "run the Movie Night scene (dims lights, closes curtains)"
```

`--param KEY=VALUE` builds the command's parameter as a JSON object
(`setPosition` uses `position`, AC `setAll` uses `mode`, `temperature`,
`fanSpeed`, `power`). For simple commands (`press`, `turnOn`, `turnOff`,
`lock`, `unlock`) omit `--param` and the default parameter `"default"` is
used, or pass `--parameter` with a raw string.

## Auth
- Provider id: `switchbot` (credential is collected as `custom.switchbot`)
- Collection: ONE combined value `token:secret` via the secure credential
  flow (`credentials.request_api_access`). In the SwitchBot app go to
  Profile > Preferences, tap the app version several times to reveal
  developer options, and copy the open token plus the secret. The CLI sends
  the token in the `Authorization` header and an HMAC-SHA256 signature of
  `token + t + nonce` (keyed by the secret) in the `sign` header, with `t`
  and `nonce` headers.
- BLE devices (Bot, Lock, Curtain, Blind Tilt) need a SwitchBot Hub with
  cloud services enabled to be reachable through this API.
- Allowed hosts: `api.switch-bot.com`
- Status check: `bin/switchbot.py auth`

## Operating Rules
1. **HIGH actuations are blocked without explicit confirmation.** `lock` and
   `unlock` on a SwitchBot Lock, and scene executions, require
   `--confirm "<exact physical effect>"` on every run. Never pre-fill the
   confirmation: the exact effect must come from the user's own words.
2. **MEDIUM actuations confirm on first use per device.** Bot `press`
   (physically presses a real button), plug and light toggles, and AC
   commands (`setAll`, `setMode`) need `--confirm` the first time a device
   is actuated; the CLI records it locally
   (`~/.config/muse-connectors/switchbot/confirmed.json`) and later runs
   proceed.
3. **LOW actuations proceed with a logged notice.** Curtain and Blind Tilt
   moves (`setPosition`) print a notice to stderr and run without
   confirmation.
4. A scene's physical effects are whatever the user saved into it. Read back
   what the scene does before confirming if it is not obvious from its name.
5. Reads (`auth`, `devices`, `status`, `scenes`) never need confirmation.
6. **Rate limit:** about 10,000 requests/day. Poll `status` sparingly.
7. **Open item:** the HMAC signature is computed over the credential
   surrogate as delivered by the credential store. Confirm the signature
   verifies against SwitchBot's servers on first live use before trusting
   signed calls.
8. Never exfiltrate the credential: the CLI only ever handles surrogates. Do
   not print, log, or transmit the token or secret values.

## Files
- SKILL.md
- bin/switchbot.py

## Maturity
🧪 Draft: written from SwitchBot's public OpenAPI v1.1 docs; not yet
live-tested end-to-end. The signature-header construction and the command
parameter shapes are untested against real SwitchBot devices.
