---
name: "home-assistant"
description: "Read entity states and call services on your Home Assistant instance. Service calls are confirmed first. Trigger phrases: home assistant, smart home, turn on the light."
metadata: { "includeInPrompt": true }
tagline: "Read entity states and call services on your Home Assistant instance. Service calls are confirmed first."
catalog_auth: "Home Assistant long-lived access token (per-user, Profile \u2192 Security \u2192 Long-Lived Access Tokens)"
catalog_hosts: ["your instance host"]
---

# Home Assistant

## Purpose
Talk to the user's own Home Assistant instance: list entity states (`states`, optionally filtered by domain), read one entity (`state`), and call services (`call`: e.g. `light.turn_on`). The instance URL is passed with every command via `--instance`.

## Tooling
All commands go through `bin/home-assistant.py`:

```bash
bin/home-assistant.py --instance https://home.example.com states                  # all entity states (entity_id, state)
bin/home-assistant.py --instance https://home.example.com states --domain light   # lights only
bin/home-assistant.py --instance https://home.example.com state --entity light.living_room
bin/home-assistant.py --instance https://home.example.com call --domain light --service turn_on --entity light.living_room
bin/home-assistant.py --instance https://home.example.com call --domain climate --service set_temperature --entity climate.living_room --data '{"temperature": 22}'
```

## Auth
- Provider id: `home-assistant` (credential is collected as `custom.home-assistant`)
- Collection: long-lived access token via the secure credential flow (`credentials.request_api_access`): create one in Home Assistant → your profile (bottom left) → Security → Long-Lived Access Tokens. Note: Home Assistant accepts tokens from any user account; for a shared household, a dedicated "automation" user keeps permissions clear.
- Connect placement: `bearer_header`
- Allowed hosts: the user's instance host (declared at connect time, e.g. `home.example.com`); the CLI derives it from `--instance`
- Status check: `bin/home-assistant.py --instance <url> states` (a successful list proves the token works)

## Operating Rules
1. `call` acts on the physical home (lights, locks, climate). Confirm the exact domain, service, entity, and parameters with the user before calling, unless standing permission exists.
2. Reading (`states`, `state`) needs no confirmation.
3. Keep `--instance` secret-adjacent: it names the user's home server. Do not post it anywhere public.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/home-assistant.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/home-assistant.py

## Maturity
🧪 Draft: written from Home Assistant's public REST API docs; not yet live-tested end-to-end.
