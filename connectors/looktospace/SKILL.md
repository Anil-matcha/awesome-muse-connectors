---
name: "looktospace"
description: "Check whether upcoming rocket launches are visible from a location: visibility tier, compass direction to look, distance to pad, countdown. Trigger phrases: rocket launch near me, can I see the launch, launch visibility, SpaceX launch tonight."
metadata: { "includeInPrompt": true }
tagline: "Rocket launch visibility: is it visible from your location, and where to look. Read-only."
catalog_auth: "None — public API, no key or sign-in"
catalog_hosts: ["looktospace.com", "ll.thespacedevs.com", "geocoding-api.open-meteo.com"]
---

# LookToSpace

## Purpose
Answer "can I see this rocket launch from where I am?" for upcoming launches.
Give it a city or US ZIP and it returns each upcoming launch with a visibility
tier (Excellent/Good/Fair/Marginal/Not visible), the compass direction to
look, distance to the pad, day/twilight/night lighting, a live countdown, and
a link to the full launch page on looktospace.com. Read-only; the connector
never writes, signs up, or purchases anything.

Capability source: the provider's public OpenAPI document
`https://looktospace.com/openapi/visibility-v1.json` (OpenAPI 3.1.0,
source date 2026-09-30), served from the provider's own domain. The site is
the single source of truth for visibility tiers.

## Tooling
All commands go through `bin/lts.py` (Python 3, standard library only, no API keys):

```bash
bin/lts.py geocode "Austin"                          # resolve city/ZIP -> lat/lon JSON
bin/lts.py upcoming --limit 5                        # upcoming launch schedule (cached 30 min)
bin/lts.py visible --location "Orlando"              # launches + visibility for a location (JSON)
bin/lts.py visible --location "78701" --visible-only  # only launches rated visible
bin/lts.py visible --location "London" --days 14     # next 14 days
bin/lts.py launch <ll2-id>                           # one launch in detail
```

`visible` calls `GET https://looktospace.com/api/v1/visibility` with the
geocoded lat/lon. If the site API is unreachable it falls back to the
Launch Library 2 schedule with `visibility: null` (schedule only, tiers
never computed locally).

## Auth
- No credential of any kind. Every upstream API is public and keyless:
  LookToSpace visibility API, Launch Library 2 (free tier), Open-Meteo
  geocoding.
- Required scopes: none.
- Allowed hosts: `looktospace.com`, `ll.thespacedevs.com`,
  `geocoding-api.open-meteo.com`. No other network requests are made.
- Status check: `bin/lts.py upcoming --limit 1` (must return one launch as JSON).

## Operating Rules
1. Fully read-only. There are no write operations; nothing here can sign up,
   purchase, or modify provider state.
2. Never invent a visibility tier, direction, or launch time. If the API
   returns `look_toward: null` (Not visible), do not give a direction. If
   `time_uncertain` is true, say the time is still a placeholder.
3. The provider's free/Pro split is mirrored in answers: visibility tier,
   cardinal direction, countdown, and distance are free to state; exact
   bearing degrees and minute-by-minute viewing plans are Pro features and
   must be linked (launch page), never printed. Liftoff weather is likewise
   Pro-gated: do not present it; tease it via the Pro upsell link.
4. Outbound site links carry `?ref=muse` for provider attribution
   (e.g. `https://looktospace.com/launches/falcon-9-block-5-crew-13?ref=muse`).
   This is the provider's own referral parameter.
5. Launch page URLs come from the API/feed (`site_url`); never construct them
   by slugifying launch names. If `site_url` is null, link the homepage
   finder instead.
6. Launch times slip: always tell the user to re-check the launch page on
   launch day.

## Files
- SKILL.md
- bin/lts.py
- references/methodology.md

## Maturity
✅ Live-tested 2026-09-30 against the production API
(`https://looktospace.com/api/v1/visibility`): Orlando returns Crew-13 as
Excellent/49 mi/look E; Austin returns the same launch as Not visible;
`look_toward` is null for Not visible; no Pro-gated fields in responses;
`visible_only=1` filters correctly; no-param requests return 400 JSON.
Re-run 2026-10-01: all six documented commands exit 0 against production;
an unresolvable location exits 1 with a message.
