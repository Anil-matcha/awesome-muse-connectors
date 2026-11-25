---
name: "tally"
description: "Read and write Tally: list forms, fetch a form, create and update forms, read submissions. Trigger phrases: tally, forms."
metadata: { "includeInPrompt": true }
tagline: "List forms, read submissions, manage form blocks."
catalog_auth: "API key (per-user; free on all plans)"
catalog_hosts: ["api.tally.so"]
---

# Tally

## Purpose
Work with Tally forms: list forms, fetch one with its full blocks, create a new form, replace a form's blocks, and read submissions. Use when the user mentions Tally or their forms.

## Tooling
All commands go through `bin/tally.py`:

```bash
bin/tally.py auth                          # verify the API key
bin/tally.py forms                         # list forms
bin/tally.py form --id "abc123"            # fetch a form with its blocks
bin/tally.py create --name "Signup"        # create a form
bin/tally.py update --id "abc123" --blocks-file blocks.json  # replace blocks
bin/tally.py submissions --id "abc123" --limit 25            # read submissions
```

The Tally API is free on all plans.

## Auth
- Provider id: `tally` (credential is collected as `custom.tally`)
- Collection: API key (`tly-...`) via the secure credential flow (`credentials.request_api_access`); created in Tally under Settings > API
- Allowed hosts: `api.tally.so`
- Status check: `bin/tally.py auth` (must return `"ok": true`)

## Operating Rules
1. `create` and `update` are writes: confirm with the user first, unless standing permission exists.
2. `update` PATCHes the form, and PATCH replaces the entire blocks array: always run `form --id` first, edit the fetched blocks, save the full new array to a file, and pass that file as `--blocks-file`. Skipping the fetch step wipes blocks you did not mean to touch.
3. Reading (forms, form, submissions) needs no confirmation.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/tally.py

## Maturity
🧪 Draft: written from Tally's public API docs; not yet live-tested end-to-end.
