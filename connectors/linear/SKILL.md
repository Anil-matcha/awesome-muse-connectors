---
name: "linear"
description: "Work with Linear: view your assigned issues and create issues. Trigger phrases: linear, linear issue, ticket."
metadata: { "includeInPrompt": true }
tagline: "View your assigned issues and create issues, over Linear's GraphQL API."
catalog_auth: "Linear personal API key (per-user, linear.app/settings/api)"
catalog_hosts: ["api.linear.app"]
---

# Linear

## Purpose
Work with the user's Linear workspace over GraphQL: view your assigned issues and create new issues. Use when the user mentions Linear or wants an issue created or checked.

## Tooling
All commands go through `bin/linear.py`:

```bash
bin/linear.py auth                                            # verify the connection (viewer query)
bin/linear.py issues                                          # your assigned issues (title, state, team)
bin/linear.py create --team-id TEAM_UUID --title "T" \
    --description "details"                                   # create an issue
```

Get a team's UUID from the Linear UI (team settings) or ask the user.

## Auth
- Provider id: `linear` (credential is collected as `custom.linear`)
- Collection: Linear personal API key via the secure credential flow (`credentials.request_api_access`); create one at linear.app/settings/api
- Required scopes: n/a (personal API keys carry your full account access: guard accordingly)
- Allowed hosts: `api.linear.app`
- Status check: `bin/linear.py auth` (must print your name and email)

## Operating Rules
1. `create` is a write: confirm the team, title, and description with the user before creating, unless standing permission to file issues exists.
2. Reading (auth, issues) needs no confirmation.
3. Linear rate-limits GraphQL; if a call returns 429, back off and retry once.
4. The personal API key has full account access: treat it as sensitive as a password. The CLI only ever handles surrogates (see `bin/linear.py`); do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/linear.py

## Maturity
🧪 Draft: written from Linear's public GraphQL API docs; not yet live-tested end-to-end.
