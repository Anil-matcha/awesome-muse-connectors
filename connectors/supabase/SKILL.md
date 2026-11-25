---
name: "supabase"
description: "Read and write a Supabase Postgres database over PostgREST: list tables, query, insert, update, and delete rows. Trigger phrases: supabase, supabase table, query supabase."
metadata: { "includeInPrompt": true }
tagline: "List tables, query rows, and insert/update/delete rows in your Supabase Postgres database."
catalog_auth: "service_role key (per-user, project Settings \u2192 API)"
catalog_hosts: ["<ref>.supabase.co"]
---

# Supabase

## Purpose
Read and write the user's Supabase project database through PostgREST: list tables, query rows, and insert/update/delete rows. Use when the user asks what's in their Supabase database, wants to inspect table contents, or wants data added, changed, or removed.

## Tooling
All commands go through `bin/supabase.py`. Every command takes the global `--project-ref` (the 20-character ref in the project URL `https://<ref>.supabase.co`):

```bash
bin/supabase.py --project-ref abcdefghijklmnopqrst tables
bin/supabase.py --project-ref abcdefghijklmnopqrst query --table profiles --limit 20

# Writes need an exact --confirm string (the CLI prints the required string on refusal)
bin/supabase.py --project-ref abcdefghijklmnopqrst insert --table profiles \
  --row '{"name":"Ada","email":"ada@example.com"}' --confirm 'insert 1 row(s) into profiles'

bin/supabase.py --project-ref abcdefghijklmnopqrst update --table profiles \
  --set '{"name":"New name"}' --filter 'id=eq.123' --confirm 'update rows in profiles where id=eq.123'

bin/supabase.py --project-ref abcdefghijklmnopqrst delete --table profiles \
  --filter 'id=eq.123' --confirm 'delete rows in profiles where id=eq.123'
```

`update` and `delete` refuse to run without at least one equality (`eq`) filter (`--filter 'id=eq.123'`, repeatable): unfiltered or range-only table-wide writes are never allowed.

## Auth
- Provider id: `supabase` (credential is collected as `custom.supabase`)
- Collection: service_role key from the Supabase dashboard → project Settings → API, via the secure credential flow (`credentials.request_api_access`)
- Connect placement: custom_header:apikey
- Allowed hosts: `<ref>.supabase.co` (per project ref)
- Status check: `bin/supabase.py --project-ref <ref> tables` (must return table names)

## Operating Rules
1. Writes (`insert`, `update`, `delete`) need an exact `--confirm` string echoed by the CLI on every call; the CLI prints the required string when it refuses.
2. `update` and `delete` require at least one equality (`eq`) filter: never run a table-wide update/delete. Filters use PostgREST syntax `COLUMN=op.value` (eq, neq, gt, gte, lt, lte, like, ilike, is, in).
3. Reading needs no confirmation.
4. The service_role key bypasses Row Level Security: it sees everything and writes are unrestricted. Only share row contents the user asked for, and never paste them into public channels.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/supabase.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/supabase.py

## Maturity
🧪 Draft: written from Supabase's public PostgREST docs (including the write endpoints); not yet live-tested end-to-end.
