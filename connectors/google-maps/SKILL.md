---
name: "google-maps"
description: "Directions with live traffic, travel times, and geocoding via Google Maps Platform Routes + Geocoding APIs. Trigger phrases: directions, how long to get to, travel time, traffic, geocode, coordinates for."
metadata: { "includeInPrompt": true }
tagline: "Routes with traffic, travel times, and geocoding — with quota caps that keep it inside the free tier."
catalog_auth: "API key (per-user) via the secure credential flow"
catalog_hosts: ["routes.googleapis.com", "maps.googleapis.com"]
---

# Google Maps Platform (Routes + Geocoding)

## Purpose
Compute routes with live traffic durations and forward/reverse geocoding through Google Maps Platform directly, instead of slower indirect routes. Use for directions, travel times, ETAs with traffic, and address ↔ coordinate conversion. This lane is routing and geocoding only — not place discovery. Read-only; there are no writes.

Source: Google Maps Platform Routes API and Geocoding API documentation (developers.google.com/maps), checked 2026-10-19.

## Tooling
All commands go through `bin/maps_call.py`:

```bash
bin/maps_call.py auth                                        # verify the stored credential answers
bin/maps_call.py route --from "Astoria, NY" --to "111 8th Ave, New York, NY" [--mode DRIVE|TRANSIT|WALK|BICYCLE]
bin/maps_call.py geocode --address "350 5th Ave, New York, NY"
bin/maps_call.py reverse --lat 40.7484 --lng -73.9857
```

## Auth
- Provider id: `google-maps` (credential is collected as `custom.google-maps`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Setup: in Google Cloud Console, enable the Routes API and Geocoding API, link a billing account, and restrict the key to those two APIs only.
- Required scopes: none (API key, no OAuth)
- Allowed hosts: `routes.googleapis.com`, `maps.googleapis.com`
- Status check: `bin/maps_call.py auth`

## Operating Rules
1. Read-only. No confirmation needed for reads.
2. Never print, log, or persist the raw API key; it rides as the `key` query parameter through the credential surrogate, only to the allowed hosts.
3. Keep usage inside the free tier with per-day quota caps in Cloud Console (budget alerts do not stop usage; quotas do). Proven caps: Routes 150 requests/day + 150 matrix elements/day (≈4,650/month vs the 5,000 free cap); Geocoding 300/day (≈9,300/month vs the 10,000 free cap). Never raise caps or enable additional Maps APIs silently — that is a user decision.
4. A 403 about billing means the project's billing account broke. A 403/429 about quota means the daily cap is hit: report it and stop for the day; do not retry around it.
5. Do not use this connector for place search/reviews/photos; it has no Places API access by design.

## Files
- SKILL.md
- bin/maps_call.py

## Maturity
✅ Live — tested against the real API on 2026-10-19; in daily production use for directions and traffic ETAs.
