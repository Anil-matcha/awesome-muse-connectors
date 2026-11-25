---
name: "patreon"
description: "Read Patreon campaigns, members, tiers, and identity (read-only). Trigger phrases: patreon, patrons, members, campaign earnings, membership tiers."
metadata: { "includeInPrompt": true }
tagline: "Read Patreon campaigns, members, tiers, and identity (read-only)."
catalog_auth: "Creator's Access Token via the secure credential flow"
catalog_hosts: ["www.patreon.com"]
---

# Patreon

## Purpose
Read the user's Patreon membership business: identity, campaigns, members, and tiers. Patreon's API is effectively read-only for creators, so this connector reads only and carries zero write risk. Use when the user mentions Patreon, patrons, or membership earnings.

## Tooling
All commands go through `bin/patreon.py`:

```bash
bin/patreon.py auth                                      # verify the access token
bin/patreon.py identity --include memberships,campaign   # show the current user
bin/patreon.py campaign --campaign-id 123456            # show a campaign
bin/patreon.py members --campaign-id 123456 --limit 25  # list campaign members
bin/patreon.py tiers --campaign-id 123456 --limit 25    # list membership tiers
```

## Auth
- Provider id: `patreon` (credential is collected as `custom.patreon`)
- Collection: Creator's Access Token via the secure credential flow (`credentials.request_api_access`); issued self-serve from the Patreon client portal, no app review needed for your own data
- Allowed hosts: `www.patreon.com`
- Status check: `bin/patreon.py auth` (must return `"ok": true`)

## Operating Rules
1. This connector is read-only by construction: Patreon exposes no creator write endpoints, so there is nothing to confirmation-gate. Never invent a write the API does not have.
2. Platform fees are tiered by plan (roughly 5-12%) plus payment processing, and the API surfaces campaign totals rather than a live ledger.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/patreon.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/patreon.py

## Maturity
🧪 Draft: written from Patreon's public API docs; not yet live-tested end-to-end.
