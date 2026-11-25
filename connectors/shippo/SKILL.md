---
name: "shippo"
description: "Get multi-carrier shipping rates, buy postage labels, track parcels, and refund labels via Shippo. Trigger phrases: shippo, shipping label, postage, shipping rates, track package."
metadata: { "includeInPrompt": true }
tagline: "Ship through many carriers (USPS, UPS, FedEx, DHL and others) with one API: get rates for a shipment; buy a printable postage label; track a parcel; refund unused labels. Reach for this when the user needs to price or purchase shipping for a package."
catalog_auth: "API token via the secure credential flow"
catalog_hosts: ["api.goshippo.com"]
---

# Shippo

## Purpose
Ship through many carriers (USPS, UPS, FedEx, DHL and others) with one API: get rates for a shipment; buy a printable postage label; track a parcel; refund unused labels. Reach for this when the user needs to price or purchase shipping for a package.

## Tooling
All commands go through `bin/shippo.py`:

```bash
bin/shippo.py auth                                    # verify the API token
bin/shippo.py rates --file shipment.json              # rates for a shipment (no label bought)
bin/shippo.py get-shipment --id SHIPMENT_ID           # retrieve a shipment
bin/shippo.py track --carrier usps --number 940011... # tracking status
bin/shippo.py buy --shipment-id SHIPMENT_ID --rate-id RATE_ID \  # buy a label from a rate
    --confirm "buy 12.40 USD USPS Priority label for rate RATE_ID"  # confirmation required
bin/shippo.py buy --shipment-id SHIPMENT_ID --rate-id RATE_ID \
    --live \                                                        # production key path: --live AND --confirm
    --confirm "buy 12.40 USD USPS Priority label for rate RATE_ID"
bin/shippo.py refund --transaction-id TXN_ID          # refund/void an unused label
```

`shipment.json` holds a Shippo shipment object: `address_from`, `address_to`, and `parcels`. `rates` never buys anything; only `buy` spends money.

## Auth
- Provider id: `shippo` (credential is collected as `custom.shippo`)
- Collection: API token via the secure credential flow (`credentials.request_api_access`); issued in the Shippo dashboard
- Auth scheme: token in the `Authorization` header (raw token, no `Bearer` prefix); this is the documented scheme and the credential config places it there
- Allowed hosts: `api.goshippo.com`
- Status check: `bin/shippo.py auth`
- Honesty note: the research dossier flagged the exact header name as a build-time open item; the dossier's own documented scheme is the raw token in `Authorization`, which is what this connector implements. Re-verify against docs.goshippo.com before relying on it in production.

## Operating Rules
1. **Test keys are the default path.** Test keys generate free test labels marked `was_test`; nothing is billed. Use them for every dry run.
2. **Production label purchase is a HIGH actuation:** `POST /transactions` buys real postage immediately, the account is billed, and the label authorizes physical transport of the parcel. The CLI enforces the gate: the `buy` command resolves the rate from the shipment, echoes the exact confirmation string (carrier, service, amount, rate id), and refuses to call the purchase endpoint until `--confirm` matches that string exactly. Passing `--live` is additionally required when the stored key is a production key; it is your explicit acknowledgment that real money will move.
3. Always show the user the rate details (carrier, service, price, delivery estimate) before asking them to confirm a purchase.
4. **Refunds:** a label can only be refunded/voided within carrier-specific windows and only if unused. Once the parcel is inducted into the carrier network, the postage is spent and cannot come back.
5. Rate limits are plan-based. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/shippo.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/shippo.py

## Maturity
Draft: written from Shippo's public API docs; not yet live-tested end-to-end.
