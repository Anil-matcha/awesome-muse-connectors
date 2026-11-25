---
name: "lemon-squeezy"
description: "Read Lemon Squeezy revenue: list orders, subscriptions, customers, products; create checkout links. Trigger phrases: lemon squeezy, store orders, revenue, checkout link."
metadata: { "includeInPrompt": true }
tagline: "Read Lemon Squeezy revenue: list orders, subscriptions, customers, products; create checkout links."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.lemonsqueezy.com"]
---

# Lemon Squeezy

## Purpose
Read the user's Lemon Squeezy store: list orders, subscriptions, customers, and products. Create checkout links on confirmation. Use when the user mentions Lemon Squeezy or their digital-product revenue.

## Tooling
All commands go through `bin/lemon-squeezy.py`:

```bash
bin/lemon-squeezy.py auth                                      # verify the API key
bin/lemon-squeezy.py orders --limit 25                         # list orders
bin/lemon-squeezy.py subscriptions --limit 25                  # list subscriptions
bin/lemon-squeezy.py customers --limit 25                     # list customers
bin/lemon-squeezy.py products --limit 25                      # list products
bin/lemon-squeezy.py checkout-create --json '{"data":{"type":"checkouts","attributes":{...}}}'  # create checkout (confirm first)
```

Reads accept `--store-id`, `--status`, and (customers) `--email` filters.

## Auth
- Provider id: `lemon-squeezy` (credential is collected as `custom.lemon-squeezy`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created in Lemon Squeezy under Settings > API. Test-mode keys exist for safe testing.
- Allowed hosts: `api.lemonsqueezy.com`
- Status check: `bin/lemon-squeezy.py auth` (must return `"ok": true`)

## Operating Rules
1. Lemon Squeezy is the merchant of record: ~5% + 50c per transaction, and it handles global sales tax and VAT. Reads move no money.
2. `checkout-create` creates a real payment link: confirm the product, variant, and price with the user before creating, unless standing permission exists. Same for subscription cancellations and refunds.
3. Responses are JSON:API (nested `data.attributes`); the CLI flattens them for display.
4. Reads need no confirmation.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/lemon-squeezy.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/lemon-squeezy.py

## Maturity
🧪 Draft: written from Lemon Squeezy's public API docs; not yet live-tested end-to-end.
