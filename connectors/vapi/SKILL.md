---
name: "vapi"
description: "Manage Vapi voice AI: assistants, phone numbers, calls. Outbound calls are high actuation and need exact-match confirmation; test numbers by default. Trigger phrases: vapi, voice assistant, outbound call, AI phone call."
metadata: { "includeInPrompt": true }
tagline: "Manage voice AI assistants, phone numbers, and calls. Outbound calls need exact-match confirmation; test numbers by default."
catalog_auth: "API key (per-user)"
catalog_hosts: ["api.vapi.ai"]
---

# Vapi

## Purpose
Manage Vapi voice-AI assistants, phone numbers, and calls: list assistants, inspect one assistant, list phone numbers, place an outbound call, and list or retrieve calls. Reach for this when the user wants to test a voice assistant or run an outbound calling flow.

## Tooling
All commands go through `bin/vapi.py`:

```bash
bin/vapi.py auth                                              # verify the API key
bin/vapi.py assistants --limit 25                             # list assistants
bin/vapi.py assistant-get --assistant-id ASST_ID               # one assistant
bin/vapi.py phone-numbers --limit 25                          # list phone numbers
bin/vapi.py call-create --assistant-id ASST_ID \
    --phone-number-id NUM_ID --customer-number +14155551234 \
    --confirm "place outbound call from NUM_ID to +14155551234"  # outbound call (HIGH)
bin/vapi.py call-get --call-id CALL_ID                        # one call
bin/vapi.py call-list --limit 25                              # list calls
```

## Auth
- Provider id: `vapi` (credential is collected as `custom.vapi`)
- Collection: API key (Vapi dashboard > API keys) via the secure credential flow (`credentials.request_api_access`)
- Auth scheme: `Authorization: Bearer <api key>` on every request
- Allowed hosts: `api.vapi.ai`
- Status check: `bin/vapi.py auth`

## Operating Rules
1. **Outbound calls are HIGH actuations.** A call dials a real phone number and costs money. `call-create` requires `--confirm` with the exact string the CLI echoes (it names the originating phone-number id and the customer number) on every call. Missing or mismatched confirmation refuses the call.
2. **Default to test phone numbers.** Vapi has no separate sandbox API; every call through the API is real. Use a Vapi number designated for testing while iterating, and switch to a production number only when the user explicitly names it. The confirmation string always shows the originating number, so a production number is never dialed by accident.
3. Surface the choice before placing a call: the assistant, the from number, and the to number. Never lock the user into a preference you chose; if the number to dial is ambiguous, ask.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/vapi.py`). Do not print, log, or transmit the API key.
5. Honesty flags (unverified while building this connector): the REST resource path forms (e.g. `/assistant` vs a versioned path) were not confirmed against a live API; the CLI surfaces Vapi's own error if they differ. Vapi's test-number offering was not verified during this build; confirm the current mechanism in Vapi's docs before iterating at volume.

## Files
- SKILL.md
- bin/vapi.py

## Maturity
Draft: written from Vapi's public docs and SDK examples; not yet live-tested end-to-end.
