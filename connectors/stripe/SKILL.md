---
name: "stripe"
description: "Read-only Stripe visibility: balance, recent charges, customers. Trigger phrases: stripe, revenue, charges, balance, customers."
metadata: { "includeInPrompt": true }
tagline: "Read-only Stripe visibility: balance, recent charges, customers. No write commands ship: expanding to writes is a deliberate v2."
catalog_auth: "Stripe restricted API key (per-user, Dashboard \u2192 Developers \u2192 API keys; read-only permissions suffice)"
catalog_hosts: ["api.stripe.com"]
---

# Stripe

## Purpose
Read-only visibility into the user's Stripe account: current balance, recent charges, and customers. Use when the user asks about revenue, payments, or their Stripe balance.

## Tooling
All commands go through `bin/stripe.py`:

```bash
bin/stripe.py balance              # current available + pending balance
bin/stripe.py charges --limit 10   # recent charges
bin/stripe.py customers --limit 10 # recent customers
```

Amounts are in the charge's smallest currency unit (e.g. cents); the currency is shown alongside.

## Auth
- Provider id: `stripe` (credential is collected as `custom.stripe`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`): a Stripe **restricted** API key (Stripe Dashboard → Developers → API keys), pasted once into the hosted form
- Minimal permissions on the restricted key: read access to Balance, Charges, and Customers is enough: grant nothing more
- Allowed hosts: `api.stripe.com`
- Status check: `bin/stripe.py balance` (must return balance data)

## Operating Rules
1. **This skill is read-only by design.** It ships no write commands: no charges, refunds, or customer mutations. Expanding to writes is a deliberate v2 decision, not an accident.
2. Reading needs no confirmation.
3. Treat all financial data as sensitive: summarize for the user, never paste raw dumps into shared contexts unprompted.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/stripe.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/stripe.py

## Maturity
🧪 Draft: written from Stripe's public API docs; not yet live-tested end-to-end.
