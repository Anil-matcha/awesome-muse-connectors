---
name: "google-pollen"
description: "5-day pollen forecast by location from the Google Pollen API: per-type index (tree/grass/weed) and per-species detail. Trigger phrases: pollen, pollen forecast, allergy forecast, ragweed, tree pollen."
metadata: { "includeInPrompt": true }
tagline: "5-day pollen forecast (tree, grass, weed + species detail) for any lat/lng."
catalog_auth: "API key (per-user) via the secure credential flow"
catalog_hosts: ["pollen.googleapis.com"]
---

# Google Pollen

## Purpose
Read the Google Pollen API forecast for a location: daily Universal Pollen Index (0–5) for TREE, GRASS, and WEED types, plus per-species detail (alder, ash, birch, oak, elm, maple, ragweed, mugwort, grasses, and more) with in-season flags. Use when the user asks about pollen, allergy conditions, or planning outdoor time around allergies. Read-only; there are no writes.

Source: Google Maps Platform Pollen API documentation (developers.google.com/maps/documentation/pollen), checked 2026-10-19.

## Tooling
All commands go through `bin/pollen_call.py`:

```bash
bin/pollen_call.py auth                                   # verify the stored credential answers
bin/pollen_call.py forecast --lat 40.77 --lng -73.93      # today only
bin/pollen_call.py forecast --lat 40.77 --lng -73.93 --days 5 --json
```

## Auth
- Provider id: `google-pollen` (credential is collected as `custom.google-pollen`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Setup: in Google Cloud Console, enable the Pollen API on a project, link a billing account (required or calls fail with a billing error), and restrict the key to the Pollen API only.
- Required scopes: none (API key, no OAuth)
- Allowed hosts: `pollen.googleapis.com`
- Status check: `bin/pollen_call.py auth`

## Operating Rules
1. Read-only. No confirmation needed for reads; there is nothing to write.
2. Never print, log, or persist the raw API key. The key rides as the `key` query parameter through the credential surrogate, only to the allowed host.
3. A 401/403 is a question about the request before it is a question about the key — confirm the surrogate was attached. A billing error means the project's billing account is missing or closed, not that the key is wrong.
4. Pricing is a Pro SKU: 5,000 free requests/month, then $10/1,000 (Google rate card, checked 2026-10-19). A daily consumer poll uses ~60 requests/month. Cache daily forecasts instead of polling hourly.
5. There is no BEECH species code in this API; do not invent one.

## Files
- SKILL.md
- bin/pollen_call.py

## Maturity
✅ Live — tested against the real API on 2026-10-19; in daily production use as an allergy-forecast source.
