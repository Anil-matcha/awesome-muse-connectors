---
name: "printful"
description: "Read Printful products and orders, create orders and mockups. Trigger phrases: printful, print on demand, mockup, fulfillment, store orders."
metadata: { "includeInPrompt": true }
tagline: "Read Printful products and orders, create orders and mockups."
catalog_auth: "personal access token via the secure credential flow"
catalog_hosts: ["api.printful.com"]
---

# Printful

## Purpose
Read the user's Printful print-on-demand business: synced store products, orders, catalog products and variants, plus mockup generation. Submit fulfillment orders on confirmation. Use when the user mentions Printful, print-on-demand, or mockups.

## Tooling
All commands go through `bin/printful.py`:

```bash
bin/printful.py auth                                      # verify the token
bin/printful.py products --limit 25                       # list synced store products
bin/printful.py orders --limit 25                         # list orders
bin/printful.py order-create --json '{...}'               # submit an order (confirm first; spends money)
bin/printful.py catalog-product --id 71                   # show a catalog product and its variants
bin/printful.py mockup-create --product-id 71 --json '{...}'  # start a mockup task
```

Pass `--store-id` with any command when using an account-level token (it sends the required `X-PF-Store-Id` header); store-scoped tokens do not need it.

## Auth
- Provider id: `printful` (credential is collected as `custom.printful`)
- Collection: personal access token via the secure credential flow (`credentials.request_api_access`); created at developers.printful.com. Store-scoped or account-level; account-level tokens require `X-PF-Store-Id`.
- Allowed hosts: `api.printful.com`
- Status check: `bin/printful.py auth` (must return `"ok": true`)

## Operating Rules
1. `order-create` submits real fulfillment and spends real money (per-item fulfillment + shipping). Confirm the items, quantities, recipient, and shipping method with the user before submitting, unless standing permission exists. Never submit orders automatically.
2. There is no API fee; you pay per fulfilled item plus shipping.
3. Reading (products, orders, catalog) needs no confirmation.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/printful.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/printful.py

## Maturity
🧪 Draft: written from Printful's public API docs; not yet live-tested end-to-end.
