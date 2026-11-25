---
name: "docusign"
description: "DocuSign eSignature: draft and send signature envelopes (demo env default), check envelope status, download signed documents. Trigger phrases: docusign, send for signature, signature envelope, envelope status, signed document."
metadata: { "includeInPrompt": true }
tagline: "Draft and send signature envelopes (demo environment by default), check envelope status, and download signed documents."
catalog_auth: "OAuth 2.0 Authorization Code Grant (per-user)"
catalog_hosts: ["demo.docusign.net", "docusign.net"]
---

# DocuSign

## Purpose
Work with DocuSign's eSignature REST API v2.1: list envelopes, fetch envelope details and recipient status, prepare DRAFT envelopes (never sent automatically), send a draft envelope to signers, and download envelope documents. Every command runs against the demo environment unless you pass `--env prod`: `demo.docusign.net` sends no legally effective documents. Reach for this when the user needs to prepare, send, or track a DocuSign signature request.

## Tooling
All commands go through `bin/docusign.py`. **Demo is the default** (`--env demo`); add `--env prod` for production:

```bash
bin/docusign.py auth                                  # verify OAuth; list accounts
bin/docusign.py envelopes --from-date 2026-09-01      # list envelopes
bin/docusign.py envelope-get --envelope-id ENV_ID     # envelope details
bin/docusign.py envelope-status --envelope-id ENV_ID  # status + recipient state
bin/docusign.py envelope-create --file envelope.json \
    --confirm "create DRAFT envelope from envelope.json"   # DRAFT only
bin/docusign.py envelope-send --envelope-id ENV_ID \
    --confirm "send envelope ENV_ID to signers (legally binding signature request)"
                                                      # HIGH: has legal effect
bin/docusign.py document-download --envelope-id ENV_ID \
    --document-id combined --out signed.pdf           # download documents
```

`envelope-create` takes a DocuSign envelope definition in JSON and forces `"status": "created"` so it always lands as a draft. `--document-id combined` downloads the full envelope as one file. `--account-id` overrides the default account from `/oauth/userinfo` on any command that needs one.

## Auth
- Provider id: `docusign` (credential is collected as `custom.docusign`)
- Collection: OAuth 2.0 Authorization Code Grant via the secure credential flow (`credentials.request_api_access`); the integration key must be registered in the DocuSign Apps and Keys page. The runtime performs the token exchange/refresh and hands the CLI a fresh Bearer token.
- Required scopes: `signature`, `extended`. Honesty flag: this scope list is taken from DocuSign's public OAuth docs and has not been verified in a live flow.
- Allowed hosts: `demo.docusign.net`, `docusign.net`, `account.docusign.com`
- Account discovery: the CLI resolves the account id and base URI from `account.docusign.com/oauth/userinfo` (the user's default account, or `--account-id`). Honesty flag: this discovery flow is taken from DocuSign's public docs and is provisional; if it fails, pass `--account-id` explicitly.
- Status check: `bin/docusign.py auth`

## Operating Rules
1. **Demo is the default and is mandatory for testing.** Never run a first-time flow against `--env prod`. The CLI cross-checks `--env` against the account's base URI and refuses a demo/prod mismatch.
2. **Sending is HIGH and has legal effect.** `envelope-send` requires `--confirm` with the exact string the CLI echoes, which names the legal effect, on every call, in demo and in production. The refusal text states it plainly: sending an envelope to signers creates a legally binding signature request.
3. **Creating is a DRAFT only.** `envelope-create` needs `--confirm` on every call too, but it never notifies signers; nothing becomes legally effective until `envelope-send`.
4. Show the exact confirmation string to the user before they run a send, so there is no ambiguity about what they are approving.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/docusign.py`). Do not print, log, or transmit the token.

## Files
- SKILL.md
- bin/docusign.py

## Maturity
Draft: written from DocuSign's public eSignature REST API v2.1 docs; not yet live-tested end-to-end.
