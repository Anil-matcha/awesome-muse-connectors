---
name: "philips-hue"
description: "Control Philips Hue lights locally: list lights and rooms, set brightness/color, activate scenes, read sensors. Trigger phrases: philips hue, hue lights, my lights."
metadata: { "includeInPrompt": true }
tagline: "Control Philips Hue lights locally: list lights and rooms, set brightness/color, activate scenes, read sensors."
catalog_auth: "Bridge pairing (local) or OAuth2 (remote)"
catalog_hosts: ["derived from --host at runtime; the CLI refuses to send the key anywhere else"]
---

# Philips Hue

## Purpose
Control the user's Philips Hue setup over the local Hue CLIP v2 API: list lights and rooms, set light state (on/off, brightness, color), set room-level grouped lights, activate scenes, and read motion, temperature, and light-level sensors. Use when the user mentions Hue or their lights.

## Tooling
All commands go through `bin/philips-hue.py` and need `--host` (the bridge base URL, e.g. `https://192.168.1.50`):

```bash
bin/philips-hue.py --host https://192.168.1.50 auth                 # verify the bridge key
bin/philips-hue.py --host https://192.168.1.50 lights               # list lights and state
bin/philips-hue.py --host https://192.168.1.50 light-set --light-id abc --on on --brightness 80 --color "#ff8800"
bin/philips-hue.py --host https://192.168.1.50 rooms                # list rooms
bin/philips-hue.py --host https://192.168.1.50 grouped-light-set --grouped-light-id abc --brightness 50
bin/philips-hue.py --host https://192.168.1.50 scene-recall --scene-id abc   # activate a scene
bin/philips-hue.py --host https://192.168.1.50 sensors --type motion # motion|temperature|light_level|all
```

## Auth
- Provider id: `philips-hue` (credential is collected as `custom.philips-hue`)
- Collection (local): no cloud key needed. Pair once: press the physical link button on the bridge, then `POST https://<bridge-ip>/api` with body `{"devicetype": "muse-connector"}`. The returned `username` is the application key; store it as `custom.philips-hue` via the secure credential flow (`credentials.request_api_access`). The CLI sends it in the `hue-application-key` header
- Collection (remote, off-network): OAuth2 Hue Remote API (see developers.meethue.com remote authentication). Same CLI contract, different host and a remote token
- Allowed hosts: derived from `--host` at runtime (the bridge's LAN IP or hostname); the CLI refuses to send the key anywhere else
- Status check: `bin/philips-hue.py --host <url> auth` (must return `"ok": true`)
- Bridge discovery: mDNS on the LAN, or https://discovery.meethue.com
- TLS: the bridge presents a self-signed certificate. If Python rejects it, point `SSL_CERT_FILE` at the bridge CA certificate before running the CLI

## Operating Rules
1. Every write (`light-set`, `grouped-light-set`, `scene-recall`) acts on the physical home: confirm the exact light/room and the change with the user before running, unless standing permission exists. Whole-home changes (e.g. turning everything off) need explicit confirmation.
2. Reading (lights, rooms, sensors, auth) needs no confirmation.
3. This connector only targets CLIP v2 (`/clip/v2`). CLIP v1 is legacy and not supported.
4. The local API works only when the runtime is on the same LAN as the bridge; off-network, switch to the remote OAuth path above.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/philips-hue.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/philips-hue.py

## Maturity
🧪 Draft: written from Philips Hue's public CLIP v2 docs; not yet live-tested end-to-end.
