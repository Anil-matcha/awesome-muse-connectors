---
name: "calendly"
description: "Read and manage Calendly: list scheduled events, event types, invitees, and availability schedules; cancel bookings. Trigger phrases: calendly, my meetings, scheduled events, cancel booking."
metadata: { "includeInPrompt": true }
tagline: "Read and manage Calendly: list scheduled events, event types, invitees, and availability schedules; cancel bookings."
catalog_auth: "OAuth 2.0 via the secure credential flow"
catalog_hosts: ["api.calendly.com"]
---

# Calendly

## Purpose
Read and manage the user's Calendly: list upcoming scheduled events, event types, invitees for an event, and availability schedules; cancel bookings. Use when the user mentions Calendly, their bookings, or meeting links.

## Tooling
All commands go through `bin/calendly.py`:

```bash
bin/calendly.py auth                                          # verify the token, shows your user URI
bin/calendly.py scheduled-events --user https://api.calendly.com/users/ABC123 --count 20
bin/calendly.py event-types --user https://api.calendly.com/users/ABC123
bin/calendly.py invitees --event-uuid abc123                # invitees for one event
bin/calendly.py availability --user https://api.calendly.com/users/ABC123
bin/calendly.py cancel --event-uuid abc123 --reason "conflict"
```

`auth` returns the user URI; most commands need it as `--user`. `--event-uuid` is the last segment of the event URI. Time filters take ISO 8601, e.g. `--min-start-time 2026-09-16T00:00:00Z`.

## Auth
- Provider id: `calendly` (credential is collected as `custom.calendly`)
- Collection: OAuth 2.0 via the secure credential flow (`credentials.request_api_access`) (token endpoint `https://auth.calendly.com/oauth/token`), or a Personal Access Token from Calendly > Integrations > API & Webhooks
- Allowed hosts: `api.calendly.com`
- Status check: `bin/calendly.py auth` (must return `"ok": true`)
- API access requires a paid Calendly plan (Professional or higher); free-plan accounts get no API access at all.

## Operating Rules
1. `cancel` changes a real booking: confirm the exact event (name, time, invitee) with the user before cancelling, unless standing permission exists.
2. Reading (events, event types, invitees, availability) needs no confirmation.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/calendly.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/calendly.py

## Maturity
🧪 Draft: written from Calendly's public API docs; not yet live-tested end-to-end.
