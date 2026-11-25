---
name: "uber-direct"
description: "Quote and dispatch same-day Uber Direct courier deliveries, and check their status. Trigger phrases: uber direct, same-day delivery, dispatch courier, delivery quote."
metadata: { "includeInPrompt": true }
tagline: "Dispatch same-day couriers through Uber Direct for food, retail, grocery, or parcel deliveries. Get a price and time quote without dispatching anyone, create a delivery when the user approves, check its status, and cancel a pending one. Reach for this when the user needs something picked up and dropped off locally today."
catalog_auth: "provider OAuth 2.0 client-credentials via the secure credential flow"
catalog_hosts: ["api.uber.com"]
---

# Uber Direct

## Purpose
Dispatch same-day couriers through Uber Direct for food, retail, grocery, or parcel deliveries. Get a price and time quote without dispatching anyone, create a delivery when the user approves, check its status, and cancel a pending one. Reach for this when the user needs something picked up and dropped off locally today.

## Tooling
All commands go through `bin/uber-direct.py`. Every command takes `--customer-id` (the Uber Direct customer ID from the developer dashboard):

```bash
bin/uber-direct.py auth --customer-id CUST_ID                 # verify the credentials
bin/uber-direct.py quote --customer-id CUST_ID \
    --file quote.json                                         # price/time quote (no courier dispatched)
bin/uber-direct.py dispatch --customer-id CUST_ID \
    --file delivery.json \
    --confirm "dispatch courier: 123 Main St -> 456 Oak Ave, quoted $9.85"  # dispatch (confirmation required)
bin/uber-direct.py get --customer-id CUST_ID \
    --delivery-id DELIVERY_ID                                 # delivery status and tracking
bin/uber-direct.py cancel --customer-id CUST_ID \
    --delivery-id DELIVERY_ID \
    --confirm "cancel delivery DELIVERY_ID"                   # cancel a pending delivery
```

`quote.json` and `delivery.json` hold the Uber Direct quote/delivery payloads (pickup and dropoff addresses, contact details, package info). Always run `quote` first and show the user the price and ETA before asking them to confirm a dispatch.

## Auth
- Provider id: `uber-direct` (credential is collected as `custom.uber-direct`)
- Collection: OAuth 2.0 client-credentials via the secure credential flow (`credentials.request_api_access`); the runtime performs the token exchange and hands the CLI a fresh access token, same pattern as the slack and x connectors
- Credential split: ONE stored credential holds the developer app's client ID and client secret; the Uber Direct customer ID is NOT a secret and is passed as the `--customer-id` runtime flag because it identifies the account in the URL path (one login can own several customer IDs)
- Auth scheme: `Authorization: Bearer <token>` on every request
- Allowed hosts: `api.uber.com`
- Status check: `bin/uber-direct.py auth --customer-id CUST_ID`

## Operating Rules
1. **Sandbox is the default.** Test deliveries never dispatch real couriers. The sandbox/test flows are enabled in the Uber Direct developer dashboard; confirm sandbox semantics there before treating any test as representative.
2. **Dispatch is a HIGH actuation:** `POST /deliveries` sends a real courier to the pickup and then the dropoff, and the quoted fee is charged once the delivery is accepted. The CLI requires `--confirm` with the exact string it echoes (pickup, dropoff, quoted amount) on every dispatch, in any environment. Missing or mismatched confirmation refuses the call.
3. Always quote before dispatching: the quote response carries the fee and ETA the user approves.
4. **Cancellation:** only possible while the delivery is pending or unassigned. A cancellation fee can apply once a courier is assigned; a delivered parcel cannot be un-delivered. `cancel` requires `--confirm` every time.
5. Delivery fees vary by market and are billed to the Uber Direct account. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/uber-direct.py`). Do not print, log, or transmit the client ID or secret.

## Files
- SKILL.md
- bin/uber-direct.py

## Maturity
Draft: written from Uber Direct's public API docs; not yet live-tested end-to-end.
