---
name: "calcom"
description: "Read and write Cal.com: list bookings and event types, create bookings. Trigger phrases: cal.com, my bookings, schedule a call."
metadata: { "includeInPrompt": true }
tagline: "List bookings and event types, create bookings."
catalog_auth: "personal API key (per-user, keys start `cal_` / `cal_live_`)"
catalog_hosts: ["api.cal.com"]
---

# Cal.com

## Purpose
Read and write the user's Cal.com scheduling: list bookings, list event types, create bookings. Use when the user mentions Cal.com, their bookings, or wants a meeting scheduled.

## Tooling
All commands go through `bin/calcom.py`:

```bash
bin/calcom.py auth                                      # verify the API key
bin/calcom.py bookings --limit 25                       # list bookings
bin/calcom.py bookings --status cancelled --limit 25    # filter by status
bin/calcom.py event-types                               # list event types
bin/calcom.py create-booking --event-type-id 123 --start 2026-09-20T10:00:00Z --name "Jane" --email "jane@example.com"
```

## Auth
- Provider id: `calcom` (credential is collected as `custom.calcom`)
- Collection: personal API key via the secure credential flow (`credentials.request_api_access`); created in Cal.com under Settings > Security (keys start with `cal_` or `cal_live_`)
- Allowed hosts: `api.cal.com`
- Status check: `bin/calcom.py auth` (must return `"ok": true`)

## Operating Rules
1. `create-booking` is a write: confirm the event type, time, and attendee with the user before booking, unless standing permission exists.
2. Reading (bookings, event-types) needs no confirmation.
3. Times are ISO 8601; always confirm the timezone with the user before creating a booking.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/calcom.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/calcom.py

## Maturity
🧪 Draft: written from Cal.com's public API docs; not yet live-tested end-to-end.
