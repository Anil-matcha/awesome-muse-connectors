---
name: "tesla-powerwall"
description: "Monitor and control Tesla Powerwall and energy sites through the Tesla Fleet API: live power status, backup reserve, operation mode, storm watch. Trigger phrases: tesla powerwall, powerwall, tesla energy, backup reserve, storm watch."
metadata: { "includeInPrompt": true }
tagline: "Monitor and control Tesla energy sites (Powerwall, solar) through the official Tesla Fleet API. Read live power flows, battery state, and site settings; change backup reserve percentage, operation mode, and Storm Watch. Use when the user mentions their Powerwall, Tesla energy site, backup reserve, or storm mode."
catalog_auth: "provider OAuth 2.0 via the secure credential flow"
catalog_hosts: ["fleet-api.prd.na.vn.cloud.tesla.com", "fleet-api.prd.eu.vn.cloud.tesla.com", "fleet-api.prd.cn.vn.cloud.tesla.com"]
---

# Tesla Powerwall

## Purpose
Monitor and control Tesla energy sites (Powerwall, solar) through the official Tesla Fleet API. Read live power flows, battery state, and site settings; change backup reserve percentage, operation mode, and Storm Watch. Use when the user mentions their Powerwall, Tesla energy site, backup reserve, or storm mode.

This connector covers energy devices only. Vehicle control lives in the separate `tesla-fleet-api` connector (different credential, different scope set).

## Tooling
All commands go through `bin/tesla-powerwall.py`. `--region` selects the API region (`na`, `eu`, `cn`; default `na`).

```bash
bin/tesla-powerwall.py auth                                  # verify the OAuth token
bin/tesla-powerwall.py sites                                 # list energy sites
bin/tesla-powerwall.py status --site-id 1234567890           # live power: solar, battery, grid, load
bin/tesla-powerwall.py site-info --site-id 1234567890        # site info and settings
bin/tesla-powerwall.py history --site-id 1234567890 --kind energy --period day \
    --start-date 2026-09-01T00:00:00-07:00 --end-date 2026-09-16T00:00:00-07:00

# MEDIUM actuations: first use per site needs --confirm "<exact effect>"
bin/tesla-powerwall.py set-reserve --site-id 1234567890 --percent 20 \
    --confirm "set backup reserve to 20% on site 1234567890"
bin/tesla-powerwall.py set-mode --site-id 1234567890 --mode self_consumption \
    --confirm "set operation mode to self_consumption on site 1234567890"
bin/tesla-powerwall.py storm-mode --site-id 1234567890 --enable \
    --confirm "enable storm watch on site 1234567890"
```

Modes for `set-mode`: `self_consumption` (self-powered), `backup` (backup-only), `autonomous` (time-based control).

After the first confirmed run on a site, the CLI records the confirmation locally (`~/.cache/muse-connectors/tesla-powerwall/confirmed.json`) and later runs proceed without asking again.

## Auth
- Provider id: `tesla-powerwall` (credential is collected as `custom.tesla-powerwall`)
- Collection: provider OAuth (OAuth 2.0 authorization-code) via the secure credential flow (`credentials.request_api_access`); this is the same OAuth pattern the `slack` and `x` connectors use
- Required scopes: `openid`, `offline_access`, `energy_device_data`, `energy_cmds`
- Allowed hosts: `fleet-api.prd.na.vn.cloud.tesla.com`, `fleet-api.prd.eu.vn.cloud.tesla.com`, `fleet-api.prd.cn.vn.cloud.tesla.com` (selected with `--region`)
- Status check: `bin/tesla-powerwall.py auth` (must return `"ok": true`)
- Onboarding burden: this is the heavy one. Registering a Tesla developer app needs legal business details, ownership of a verified domain, and a public key hosted at `/.well-known/appspecific/com.tesla.3p.public-key.pem`. Budget real setup time before the first call works.

## Operating Rules
1. `set-reserve`, `set-mode`, and `storm-mode` are MEDIUM actuations: they change how the battery charges and discharges, which alters outage resilience and grid behavior. Confirm on first use per site with `--confirm` naming the exact effect (the CLI enforces the exact text); reads need no confirmation.
2. Backup reserve percent must be 0 to 100. Lowering it means less stored energy during an outage; say so when confirming.
3. Storm Watch charges the battery from the grid ahead of severe weather. Enabling it changes grid import behavior; disabling it returns to normal policy.
4. Rate limits: historically about 200 requests per hour per site on the free developer tier. Keep polling modest; `status` once a minute is fine, once a second is not.
5. Time-of-use tariff writes (`time_of_use_settings`) are not shipped as a CLI command: the tariff payload is a complex nested structure that is easy to get wrong. Point the user at the official Fleet API energy docs if they need it.
6. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/tesla-powerwall.py

## Maturity
🧪 Draft: written from Tesla's public Fleet API docs; not yet live-tested end-to-end.

Honesty flags: `set-reserve` and `set-mode` paths and payloads are pinned against the official Fleet API energy reference and corroborating integrations. The `storm_mode` payload (`{"enabled": true/false}`) follows the official docs' storm mode section but has not been exercised here. Operation-mode and TOU paths were re-verified against the official docs at build time (2026-09-16); treat every write as untested until a live run confirms it.
