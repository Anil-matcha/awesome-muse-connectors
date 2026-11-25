---
name: "lob"
description: "Print and mail physical letters and postcards through Lob, verify US addresses, and cancel pieces before production. Trigger phrases: lob, send postcard, send letter, direct mail, print and mail."
metadata: { "includeInPrompt": true }
tagline: "Send physical mail through Lob's Print and Mail API: verify US addresses; create postcards and letters that get printed and mailed; list what was sent; cancel a piece while it is still before production. Reach for this when the user wants a real letter or postcard in the mail rather than an email."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.lob.com"]
---

# Lob

## Purpose
Send physical mail through Lob's Print and Mail API: verify US addresses; create postcards and letters that get printed and mailed; list what was sent; cancel a piece while it is still before production. Reach for this when the user wants a real letter or postcard in the mail rather than an email.

## Tooling
All commands go through `bin/lob.py`:

```bash
bin/lob.py auth                                   # verify the API key
bin/lob.py verify-address --file address.json     # verify/correct a US address (no mail sent)
bin/lob.py send-postcard --file postcard.json \
    --confirm "mail postcard to Jane Doe at 123 Main St"   # send a postcard (test key: simulated)
bin/lob.py send-letter --file letter.json \
    --confirm "mail letter to Jane Doe at 123 Main St"     # send a letter (test key: simulated)
bin/lob.py send-postcard --file postcard.json --live \
    --confirm "mail postcard to Jane Doe at 123 Main St"   # production key path: --live AND --confirm
bin/lob.py postcards                               # list postcards
bin/lob.py get-letter --id ltr_abc123             # retrieve a letter
bin/lob.py cancel-postcard --id psc_abc123        # cancel before production (no effect after)
bin/lob.py cancel-letter --id ltr_abc123          # cancel before production (no effect after)
```

`postcard.json` / `letter.json` hold the Lob create payloads (`to`, `from`, `front`/`back` HTML or template, `size`). Address verification never sends anything.

## Auth
- Provider id: `lob` (credential is collected as `custom.lob`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); issued in the Lob dashboard
- Auth scheme: HTTP Basic with the API key as the username and a blank password; placement is resolved by the helper from the credential config
- Allowed hosts: `api.lob.com`
- Status check: `bin/lob.py auth`
- Key types: keys beginning `test_` simulate the full lifecycle free (nothing printed, nothing charged). Keys beginning `live_` print and mail for real.

## Operating Rules
1. **Test keys are the default path.** With a `test_` key the full lifecycle is simulated free. Never send real mail on a test run.
2. **Live sends are a HIGH actuation:** `POST /postcards` and `POST /letters` with a live key print a physical piece, hand it to the postal stream, and charge printing plus postage per piece. Once a piece enters production it cannot be recalled. The CLI enforces the gate: `--live` (your explicit acknowledgment that the stored key is live and real mail will go out) AND `--confirm` with the exact string the CLI echoes (recipient and address) are both required. The string must match exactly.
3. **Cancellation only works pre-production.** `DELETE /postcards/{id}` and `DELETE /letters/{id}` cancel a piece only while it is still in a cancellable state; after production starts they do nothing and spent fees are not refunded.
4. Per-piece pricing: printing plus postage are charged per piece on live keys; current prices are published on lob.com. Always state the piece count and type when confirming a send.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/lob.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/lob.py

## Maturity
Draft: written from Lob's public API docs; not yet live-tested end-to-end.
