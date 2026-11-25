---
name: "polar"
description: "Read Polar orders, subscriptions, products, and customers; create checkouts and refunds. Trigger phrases: polar, orders, refunds, merchant of record."
metadata: { "includeInPrompt": true }
tagline: "Read Polar orders, subscriptions, products, and customers; create checkouts and refunds."
catalog_auth: "Organization Access Token via the secure credential flow"
catalog_hosts: ["api.polar.sh", "sandbox-api.polar.sh"]
---

# Polar

## Purpose
Read the user's Polar merchant-of-record business: list orders, subscriptions, products, and customers. Create checkout sessions and issue refunds on confirmation. Use when the user mentions Polar or their digital-product revenue.

## Tooling
All commands go through `bin/polar.py`:

```bash
bin/polar.py auth                                      # verify the access token
bin/polar.py orders --limit 25                         # list orders
bin/polar.py subscriptions --limit 25                  # list subscriptions
bin/polar.py products --limit 25                       # list products
bin/polar.py customers --limit 25                      # list customers
bin/polar.py checkout-create --json '{...}'            # create a checkout (confirm first)
bin/polar.py refund-create --json '{...}'              # issue a refund (confirm first)
```

Add `--sandbox` to any command to target the Polar sandbox instead of production, and `--organization-id` to scope reads.

## Auth
- Provider id: `polar` (credential is collected as `custom.polar`)
- Collection: Organization Access Token via the secure credential flow (`credentials.request_api_access`); created in the Polar org dashboard (tokens start with `polar_oat_`, scoped). Never put the OAT in a browser or a customer-facing page.
- Allowed hosts: `api.polar.sh`, `sandbox-api.polar.sh`
- Status check: `bin/polar.py auth` (must return `"ok": true`)

## Operating Rules
1. Polar is the merchant of record: 4% + 40c per transaction, no monthly fee; it handles tax. Reads move no money.
2. `checkout-create` and `refund-create` move money: confirm the product, amount, and recipient with the user before running, unless standing permission exists.
3. Rate limits are 500 req/min production and 100 req/min sandbox; on HTTP 429 the CLI reports the `Retry-After` hint, then back off.
4. Reading (orders, subscriptions, products, customers) needs no confirmation.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/polar.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/polar.py

## Maturity
🧪 Draft: written from Polar's public API docs; not yet live-tested end-to-end.
