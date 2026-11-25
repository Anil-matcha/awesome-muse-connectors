---
name: "etsy"
description: "Read Etsy shop data: receipts, listings, transactions, payment ledger; create listings. Trigger phrases: etsy, shop orders, listings, receipts, seller."
metadata: { "includeInPrompt": true }
tagline: "Read Etsy shop data: receipts, listings, transactions, payment ledger; create listings."
catalog_auth: "OAuth 2.0 via the secure credential flow"
catalog_hosts: ["openapi.etsy.com"]
---

# Etsy

## Purpose
Read the user's Etsy shop: receipts (orders), active listings, transactions, and the payment-account ledger. Create listings on confirmation. Use when the user mentions Etsy, their shop, or listing management.

## Tooling
All commands go through `bin/etsy.py`; every command needs `--shop-id`:

```bash
bin/etsy.py auth --shop-id 12345678                       # verify OAuth token and keystring
bin/etsy.py receipts --shop-id 12345678 --limit 25        # list receipts (orders)
bin/etsy.py listings --shop-id 12345678 --limit 25        # list active listings
bin/etsy.py listing-create --shop-id 12345678 --json '{...}'  # create a listing (confirm first)
bin/etsy.py transactions --shop-id 12345678 --limit 25    # list transactions
bin/etsy.py ledger --shop-id 12345678 --limit 25          # list payment-account ledger entries
```

## Auth
- Provider id: `etsy` (credential is collected as `custom.etsy`)
- Collection: OAuth 2.0 via the secure credential flow (`credentials.request_api_access`); register an app at etsy.com/developers. The app keystring is collected alongside the token as a second credential entry. The key must be approved in the Etsy developer portal before any call works.
- Allowed hosts: `openapi.etsy.com`
- Status check: `bin/etsy.py auth --shop-id <id>` (must return `"ok": true`)

## Operating Rules
1. Fee warning: creating a listing costs $0.20 per listing; sales carry a 6.5% transaction fee plus roughly 3% + 25c payment processing. Renewals, inventory changes, and price updates can cost money too.
2. `listing-create` (and any listing renewal, inventory, or price update) must be confirmed with the user before running, unless standing permission exists. Never create listings automatically.
3. Reading (receipts, listings, transactions, ledger) needs no confirmation.
4. The exact auth scheme is `Authorization: Bearer <token>` plus the keystring in the `x-api-key` header.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/etsy.py`). Do not print, log, or transmit the token or keystring value.

## Files
- SKILL.md
- bin/etsy.py

## Maturity
🧪 Draft: written from Etsy's public Open API v3 docs; not yet live-tested end-to-end.
