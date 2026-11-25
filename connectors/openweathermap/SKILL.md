---
name: "openweathermap"
description: "Current weather and 5-day forecast for any city. Trigger phrases: weather, openweathermap, forecast."
metadata: { "includeInPrompt": true }
tagline: "Current weather and 5-day forecast for any city. Read-only."
catalog_auth: "OpenWeatherMap API key (per-user, openweathermap.org \u2192 API keys; free tier fine)"
catalog_hosts: ["api.openweathermap.org"]
---

# OpenWeatherMap

## Purpose
Read-only current weather and 5-day forecast for any city, in metric units. Use when the user mentions weather, a forecast, or OpenWeatherMap.

## Tooling
All commands go through `bin/openweathermap.py`:

```bash
bin/openweathermap.py weather --city "London"     # current conditions
bin/openweathermap.py forecast --city "Lagos"     # 5-day forecast, first 8 slots
```

## Auth
- Provider id: `openweathermap` (credential is collected as `custom.openweathermap`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Get a key: openweathermap.org → API keys (free tier fine)
- Allowed hosts: `api.openweathermap.org`
- Status check: `bin/openweathermap.py weather --city "London"`
- Connect placement: `query_param:appid`

Note: new API keys can take up to 2 hours to activate after creation.

## Operating Rules
1. This connector is read-only: it only reads weather data. It never writes, modifies, or sends anything on the user's behalf.
2. Temperatures are always returned in Celsius (`units=metric`); state the units when reporting.
3. The forecast returns 3-hour slots; the CLI outputs the first 8 (roughly 24 hours ahead).
4. If a city name is ambiguous, report what the API returned (its `city` and `country`) rather than guessing.
5. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/openweathermap.py

## Maturity
🧪 Draft: written from OpenWeatherMap's public API docs; not yet live-tested end-to-end.
