---
name: "square"
description: "Work with Square: list locations and payments, create orders, push Terminal checkouts, charge payment sources, and refund payments. Trigger phrases: square, square terminal, process payment, refund payment, point of sale."
metadata: { "includeInPrompt": true }
tagline: "Work with a Square seller account: list locations and payments, create orders, push a checkout to a physical Square Terminal for in-person payment, charge a payment source directly, cancel a pending Terminal checkout, and refund a payment. Reach for this when the user needs to take or return money through Square."
catalog_auth: "provider OAuth 2.0 or personal access token via the secure credential flow"
catalog_hosts: ["connect.squareup.com", "connect.squareupsandbox.com"]
---

# Square

## Purpose
Work with a Square seller account: list locations and payments, create orders, push a checkout to a physical Square Terminal for in-person payment, charge a payment source directly, cancel a pending Terminal checkout, and refund a payment. Reach for this when the user needs to take or return money through Square.

## Tooling
All commands go through `bin/square.py`. **Sandbox is the default** (`--env sandbox`); sandbox never moves real money. Add `--env prod` for production:

```bash
bin/square.py auth                                   # verify the token (sandbox)
bin/square.py locations                              # list seller locations
bin/square.py payments --limit 10                    # list payments
bin/square.py payment-get --payment-id PAY_ID        # one payment
bin/square.py order-create --file order.json         # create an order (moves no money)
bin/square.py checkout-create --device-id DEV_ID \
    --amount-cents 1200 --currency USD \
    --confirm "present $12.00 USD charge on terminal DEV_ID"   # push charge to a Terminal
bin/square.py checkout-get --checkout-id CO_ID       # Terminal checkout status
bin/square.py checkout-cancel --checkout-id CO_ID \
    --confirm "cancel terminal checkout CO_ID"        # cancel a pending checkout
bin/square.py charge --source-id SRC_ID \
    --amount-cents 1200 --currency USD \
    --confirm "charge $12.00 USD to payment source SRC_ID"     # charge a payment source
bin/square.py refund --payment-id PAY_ID \
    --amount-cents 1200 --currency USD \
    --confirm "refund $12.00 USD on payment PAY_ID"   # send money back
```

Amounts are in the currency's smallest unit (`--amount-cents 1200` is $12.00). `order-create` takes a Square order object in JSON and creates an order record only; no money moves until a payment is attached.

## Auth
- Provider id: `square` (credential is collected as `custom.square`)
- Collection: OAuth 2.0 bearer via the secure credential flow (`credentials.request_api_access`) for third-party apps, or a personal access token for a single account; the runtime performs the token exchange/refresh and hands the CLI a fresh Bearer token, same pattern as the slack and x connectors
- Auth scheme: `Authorization: Bearer <token>` on every request
- Allowed hosts: `connect.squareup.com`, `connect.squareupsandbox.com`
- Sandbox is the CLI default and is mandatory for testing: `https://connect.squareupsandbox.com`. Switch to production only with `--env prod` on the command and a production credential stored.
- Status check: `bin/square.py auth`

## Operating Rules
1. **Sandbox is the default and is mandatory for testing.** Never run a first-time flow against `--env prod`. Confirm the flow works in sandbox, then switch.
2. **Terminal checkout and direct charges are HIGH actuations.** `POST /v2/terminals/checkouts` presents a charge on a physical Terminal; a customer tapping or inserting a card captures real funds. `POST /v2/payments` charges a payment source immediately. Both require `--confirm` with the exact string the CLI echoes (it names the amount, the currency and the target) on every call, in sandbox and in production. Missing or mismatched confirmation refuses the call.
3. **Refunds are MEDIUM and move real money back.** `POST /v2/refunds` requires `--confirm` with the exact echoed string on every call (this is stricter than the standing first-use-only rule, chosen because a mistaken refund is hard to take back).
4. Cancelling a pending Terminal checkout requires `--confirm` every time; it has no effect once the payment completed.
5. Square charges processing fees per transaction; check squareup.com pricing for current rates. Every write uses an idempotency key so retries cannot double-charge.
6. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/square.py`). Do not print, log, or transmit the token.

## Files
- SKILL.md
- bin/square.py

## Maturity
Draft: written from Square's public API docs; not yet live-tested end-to-end.
