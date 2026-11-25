---
name: "unifi-protect"
description: "Read UniFi Protect cameras, pull snapshots, and adjust camera settings (PTZ, lights, chimes). Trigger phrases: unifi protect, unifi camera, protect snapshot, unifi doorbell."
metadata: { "includeInPrompt": true }
tagline: "Read camera state and still snapshots from a local UniFi Protect console (Protect 5.3+) through the official Integration API, and adjust camera settings: PTZ position, flood lights, chimes, talkback. Use it when the user asks what their UniFi cameras see, wants a snapshot saved, or wants to change camera behavior. Everything runs against the local console; there is no cloud dependency."
catalog_auth: "integration key via the secure credential flow"
catalog_hosts: ["the host you pass via --host"]
---

# UniFi Protect

## Purpose
Read camera state and still snapshots from a local UniFi Protect console
(Protect 5.3+) through the official Integration API, and adjust camera
settings: PTZ position, flood lights, chimes, talkback. Use it when the
user asks what their UniFi cameras see, wants a snapshot saved, or wants to
change camera behavior. Everything runs against the local console; there is
no cloud dependency.

## Tooling
All commands go through `bin/unifi-protect.py`. `--host` is the console base
URL (the CLI appends `/proxy/protect/integration/v1`):

```bash
bin/unifi-protect.py --host https://192.168.1.1 auth              # status check: verify key, count cameras
bin/unifi-protect.py --host https://192.168.1.1 cameras          # list cameras and state
bin/unifi-protect.py --host https://192.168.1.1 camera --id <id> # camera detail
bin/unifi-protect.py --host https://192.168.1.1 snapshot --id <id> \
    --out ~/workspace/porch.jpg                                   # save a still image

# Writes. Camera setting updates are LOW: they proceed with a logged notice:
bin/unifi-protect.py --host https://192.168.1.1 patch --id <id> \
    --field micEnabled=true

# PTZ, lights, chime, talkback are LOW-grade but their exact write paths are
# UNTESTED open items: each prints a warning, then proceeds with a notice:
bin/unifi-protect.py --host https://192.168.1.1 ptz --id <id> --pan 10 --tilt -5
bin/unifi-protect.py --host https://192.168.1.1 lights --id <id> --on true
bin/unifi-protect.py --host https://192.168.1.1 chime --id <id>
bin/unifi-protect.py --host https://192.168.1.1 talkback --id <id>
```

Consoles commonly use self-signed TLS certificates. Verification stays ON by
default; if the console's certificate is self-signed and the user accepts the
risk, add `--insecure` to any command. The CLI warns loudly when
verification is disabled.

## Auth
- Provider id: `unifi-protect` (credential is collected as
  `custom.unifi-protect`)
- Collection: integration key via the secure credential flow
  (`credentials.request_api_access`). On the console: Protect Settings >
  Control Plane > Integrations > create an integration key. The CLI sends it
  as the `X-API-KEY` header.
- Allowed hosts: whatever `--host` names (the console's IP/hostname). The CLI
  pins egress to that host per run.
- Status check: `bin/unifi-protect.py --host <console> auth`

## Operating Rules
1. **Reads are always safe.** `auth`, `cameras`, `camera`, and `snapshot`
   never need confirmation.
2. **LOW actuations proceed with a logged notice.** `patch` (camera settings
   such as microphone or recording behavior), PTZ moves, flood-light
   on/off, chime sounding, and talkback print a notice to stderr and run.
   Arm-profile changes alter which cameras record and when: say so in the
   reply when a `patch` touches recording behavior.
3. **Open item: the PTZ / lights / chime / talkback paths are untested.** Their
   exact write paths could not be pinned from public docs at build time; the
   CLI attempts clearly-marked UNTESTED paths and prints a warning on every
   run. Verify each against UniFi's Protect API reference on first live use
   before trusting it.
4. **TLS:** keep verification on. Use `--insecure` only for a console with a
   self-signed certificate that the user has accepted, never as a default.
5. Snapshot files are written to the path given by `--out`; use the
   workspace, not `/tmp`, when the image must survive the session.
6. Never exfiltrate the credential: the CLI only ever handles surrogates. Do
   not print, log, or transmit the integration key value.

## Files
- SKILL.md
- bin/unifi-protect.py

## Maturity
🧪 Draft: written from UniFi's public Protect Integration API docs; not yet
live-tested end-to-end. Reads (`cameras`, `snapshot`) and `PATCH
/cameras/{id}` are pinned; the PTZ / talkback / lights / chime write paths
are open items and ship marked untested.
