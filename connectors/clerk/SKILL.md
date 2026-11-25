---
name: "clerk"
description: "Read and write Clerk: list users, look up a user, create, update, and delete users. Trigger phrases: clerk, users auth."
metadata: { "includeInPrompt": true }
tagline: "List, create, update, and delete users."
catalog_auth: "Secret API key (per-project)"
catalog_hosts: ["api.clerk.com"]
---

# Clerk

## Purpose
Manage users in the user's Clerk application through the Clerk Backend API: list users, look up one user, create users, update names, and delete users. Use when the user mentions their Clerk users.

## Tooling
All commands go through `bin/clerk.py`:

```bash
bin/clerk.py auth                                                    # verify the secret key
bin/clerk.py users --limit 25                                        # list users
bin/clerk.py user --id <user-id>                                     # look up one user
bin/clerk.py create --email "them@example.com" --first-name Ana      # create a user
bin/clerk.py update --id <user-id> --last-name Reyes                 # update a user
bin/clerk.py delete --id <user-id>                                    # delete a user
```

## Auth
- Provider id: `clerk` (credential is collected as `custom.clerk`)
- Collection: secret key (`sk_...`) via the secure credential flow (`credentials.request_api_access`); found in the Clerk dashboard under API Keys
- Allowed hosts: `api.clerk.com`
- Status check: `bin/clerk.py auth` (must return `"ok": true`)

## Operating Rules
1. Request bodies use snake_case field names (for example `public_metadata`). The Clerk SDKs use camelCase; keep the two conventions separate and never send SDK-style field names to this API.
2. Create, update, and delete are confirmation-gated: confirm the details with the user first, unless standing permission exists.
3. Delete is irreversible; confirm explicitly even when other writes have standing permission.
4. Reads (users, user) need no confirmation.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/clerk.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/clerk.py

## Maturity
🧪 Draft: written from Clerk's public API docs; not yet live-tested end-to-end.
