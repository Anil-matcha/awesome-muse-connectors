---
name: "sentry"
description: "Triage Sentry errors: list organizations, projects, and recent issues; resolve, archive, and assign issues. Trigger phrases: sentry, sentry errors, error tracking."
metadata: { "includeInPrompt": true }
tagline: "List organizations and projects, triage unresolved issues from the last 24h, and resolve/archive/assign issues."
catalog_auth: "auth token (per-user, sentry.io \u2192 Settings \u2192 Auth Tokens)"
catalog_hosts: ["sentry.io"]
---

# Sentry

## Purpose
Error triage for the user's Sentry: list organizations, list projects in an org, and list unresolved issues from the last 24 hours sorted by frequency. Use when the user asks what's broken, what's new in Sentry, or wants an error triaged. The `resolve`, `archive`, and `assign` commands update an issue's state.

## Tooling
All commands go through `bin/sentry.py`:

```bash
bin/sentry.py orgs                   # your organizations
bin/sentry.py projects --org myorg   # projects in an org
bin/sentry.py issues --org myorg     # unresolved issues, last 24h, by frequency

# Writes need an exact --confirm string (the CLI prints the required string on refusal)
bin/sentry.py resolve --org myorg --issue-id 123456789 \
  --confirm 'resolve issue 123456789'
bin/sentry.py archive --org myorg --issue-id 123456789 \
  --confirm 'archive issue 123456789'
bin/sentry.py assign --org myorg --issue-id 123456789 --assignee jane@example.com \
  --confirm 'assign issue 123456789 to jane@example.com'
```

`--issue-id` is the numeric `id` from the `issues` output. `--assignee` takes a user id, `user:<id>`, username, user email, or `team:<team_id>`. Note: the `archive` command sends `status="ignored"` because "archived" is not a documented API status value: it is the API's archive-equivalent (see the HONESTY NOTE in `bin/sentry.py`).

## Auth
- Provider id: `sentry` (credential is collected as `custom.sentry`)
- Collection: auth token from sentry.io → Settings → Auth Tokens, via the secure credential flow (`credentials.request_api_access`): reads need `org:read`, `project:read`, `event:read`; the write commands additionally need `event:write` (or `event:admin`) per Sentry's API docs
- Connect placement: bearer_header
- Allowed hosts: `sentry.io`
- Status check: `bin/sentry.py orgs` (must return your organizations)

## Operating Rules
1. `resolve`, `archive`, and `assign` need an exact `--confirm` string echoed by the CLI on every call; the CLI prints the required string when it refuses. Reading needs no confirmation.
2. Use the numeric `id` from `issues` output for `--issue-id`, never a shortId.
3. This skill targets sentry.io (US SaaS). EU-region (`de.sentry.io`) and self-hosted Sentry use a different host and are out of scope for this skill.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/sentry.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/sentry.py

## Maturity
🧪 Draft: written from Sentry's public API docs (including the issue-update endpoints); not yet live-tested end-to-end.
