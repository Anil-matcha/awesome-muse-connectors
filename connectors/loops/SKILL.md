---
name: "loops"
description: "Read and write Loops: find and manage email contacts; send events and transactional emails. Trigger phrases: loops, email contacts."
metadata: { "includeInPrompt": true }
tagline: "Manage email contacts, trigger loops, send transactional email."
catalog_auth: "API key (per-user)"
catalog_hosts: ["app.loops.so"]
---

# Loops

## Purpose
Manage Loops email contacts and trigger sends: look up a contact by email, keep contacts current, fire custom events for automations, and send transactional emails from a template. Use when the user mentions Loops or their email contacts.

## Tooling
All commands go through `bin/loops.py`:

```bash
bin/loops.py auth                                              # verify the API key
bin/loops.py find --email "them@example.com"                   # look up a contact
bin/loops.py create --email "them@example.com" --field firstName=Ada   # add a contact
bin/loops.py upsert --email "them@example.com" --field plan=pro        # create or update
bin/loops.py event --email "them@example.com" --name "Signed Up"       # fire an event
bin/loops.py send-email --email "them@example.com" --template-id "cm0abc123"  # transactional email
```

`--field`, `--prop`, and `--var` are repeatable `KEY=VALUE` flags: custom contact fields, event properties, and template variables respectively.

## Auth
- Provider id: `loops` (credential is collected as `custom.loops`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in Loops under Settings > API
- Allowed hosts: `app.loops.so`
- Status check: `bin/loops.py auth` (must return `"ok": true`)

## Operating Rules
1. `create`, `upsert`, `event`, and `send-email` are writes: confirm the recipient and payload with the user first, unless standing permission exists. `send-email` sends a real email; double check the template id.
2. Reading (`find`) needs no confirmation.
3. Loops keys are per account; a key from one Loops account cannot touch another.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/loops.py

## Maturity
🧪 Draft: written from Loops's public API docs; not yet live-tested end-to-end.
