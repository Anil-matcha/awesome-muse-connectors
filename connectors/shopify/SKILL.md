---
name: "shopify"
description: "Work with your Shopify store: view orders, products, customers; create products and discounts (with confirmation). No order or customer writes. Trigger phrases: shopify, shopify orders, shopify store, shopify discount."
metadata: { "includeInPrompt": true }
tagline: "View orders, products, customers; create products and discounts with confirmation. No order or customer writes, ever."
catalog_auth: "Shopify Admin API access token (per-user, Shopify admin \u2192 Apps \u2192 Develop apps \u2192 custom app; scopes read_orders/read_products/read_customers plus write_products/write_discounts for writes)"
catalog_hosts: ["<your-shop>.myshopify.com"]
---

# Shopify

## Purpose
Read the user's Shopify store (open orders, products, customers) and write in two places only: create products (as drafts, with one priced variant) and create discounts (a price rule plus a redeemable discount code). Use when the user mentions Shopify or asks about orders, products, discounts, or customers in their store. There are no order or customer write commands in this connector, ever: no money-movement writes exist here by design.

## Tooling
All commands go through `bin/shopify.py` and take `--shop` (e.g. `mystore` or `mystore.myshopify.com`; the CLI normalizes it to the full `.myshopify.com` host):

```bash
bin/shopify.py auth --shop mystore                    # verify the connection
bin/shopify.py orders --shop mystore --limit 10       # open orders
bin/shopify.py products --shop mystore --limit 10     # products
bin/shopify.py customers --shop mystore --limit 10    # customers

bin/shopify.py product-create --shop mystore --title "Tote Bag" \
    --body-html "<p>Sturdy canvas tote.</p>" --price 29.99 --sku TOTE-001 \
    --confirm 'create product "Tote Bag" at price 29.99'
bin/shopify.py discount-create --shop mystore --title "Fall Sale" \
    --percent 20 --code FALL20 --ends-at 2026-12-31T23:59:59Z \
    --confirm 'create discount "Fall Sale" (percentage -20.0) with code FALL20'
```

Products are created as **drafts** (hidden from shoppers until activated). `discount-create` creates a price rule (percentage via `--percent`, or fixed amount via `--amount`) and then attaches the `--code` as a redeemable discount code. `--ends-at` and `--usage-limit` are optional.

## Auth
- Provider id: `shopify` (credential is collected as `custom.shopify`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`)
- Token: a custom app access token from Shopify admin → Apps → Develop apps, with the `read_orders`, `read_products`, and `read_customers` scopes. **If you want the write commands, the token must be REGENERATED (or the custom app reconfigured) with the `write_products` and `write_discounts` access scopes: writes made with a read-only token fail with HTTP 403.**
- Allowed hosts: `<your-shop>.myshopify.com` (your store's own domain, set per call with `--shop`)
- Status check: `bin/shopify.py auth --shop <your-shop>` (must return `"ok": true`)
- Connect placement: `custom_header:X-Shopify-Access-Token`

## Operating Rules
1. This connector writes in exactly two places: `product-create` (new draft product with one variant) and `discount-create` (price rule + discount code). There are no order or customer write commands, and no money-movement writes of any kind, by design: do not invent them.
2. **Both write commands need exact-match confirmation on every call.** `product-create` requires `--confirm` with the exact string the CLI echoes (title + price). `discount-create` requires `--confirm` with its echoed string (title, value, code).
3. Writes 403ing usually means the custom-app token lacks `write_products`/`write_discounts`: regenerate the token with those scopes, don't guess at the endpoint.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.
5. Always pass `--shop`; the CLI only ever talks to that store's own `.myshopify.com` host.
6. Endpoint honesty flag: the write paths (`POST /products.json`, `POST /price_rules.json`, `POST /price_rules/{id}/discount_codes.json`) and the 2026-07 API version are taken from public docs/secondary sources and have not been verified in a live flow; verify against the store before relying on them.

## Files
- SKILL.md
- bin/shopify.py

## Maturity
🧪 Draft: written from Shopify's public Admin API docs; not yet live-tested end-to-end. The product-create and discount-create flows are doc-built only.
