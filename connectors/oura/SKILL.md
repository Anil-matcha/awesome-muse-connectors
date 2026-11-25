---
name: "oura"
description: "Read Oura Ring health data: sleep scores, sleep sessions, readiness, workouts, and SpO2. Trigger phrases: oura, sleep score, readiness, my sleep."
metadata: { "includeInPrompt": true }
tagline: "Read Oura Ring health data: sleep scores, sleep sessions, readiness, workouts, and SpO2."
catalog_auth: "OAuth 2.0 via the secure credential flow"
catalog_hosts: ["api.ouraring.com"]
---

# Oura

## Purpose
Read the user's Oura Ring health data: daily sleep scores, detailed sleep sessions, daily readiness, workouts, and SpO2. Use when the user mentions Oura, their sleep, or readiness.

## Tooling
All commands go through `bin/oura.py`:

```bash
bin/oura.py auth                                              # verify the OAuth token
bin/oura.py daily-readiness --start-date 2026-09-10          # readiness scores
bin/oura.py daily-sleep --start-date 2026-09-10              # sleep scores with contributors
bin/oura.py sleep --start-date 2026-09-10                    # detailed sleep sessions
bin/oura.py workouts --start-date 2026-09-10 --limit 5       # workouts
bin/oura.py daily-spo2 --start-date 2026-09-10               # blood oxygen summaries
```

Dates are `YYYY-MM-DD`; `--end-date` defaults to today, `--limit` defaults to 10.

## Auth
- Provider id: `oura` (credential is collected as `custom.oura`)
- Collection: OAuth 2.0 via the secure credential flow (`credentials.request_api_access`); register an app at developer.ouraring.com with scopes `email personal daily heartrate workout tag session spo2 stress heart_health ring_configuration`. Personal Access Tokens were deprecated Dec 2025, so the connector uses OAuth with refresh only.
- Allowed hosts: `api.ouraring.com`
- Status check: `bin/oura.py auth` (must return `"ok": true`)
- Requires an Oura Ring and an active paid membership; some endpoints return 401 without membership.

## Operating Rules
1. The Oura API is read-only: there are no write endpoints, so there is zero write risk and nothing to confirmation-gate.
2. Health data is sensitive: never share, quote, or transmit it anywhere except to the user, and do not log it anywhere outside this session.
3. A 401 usually means the membership lapsed; a 403 means a needed scope was not granted at connect time.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/oura.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/oura.py

## Maturity
🧪 Draft: written from Oura's public API v2 docs; not yet live-tested end-to-end.
