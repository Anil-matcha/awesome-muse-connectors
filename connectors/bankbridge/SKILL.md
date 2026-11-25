---
name: "bankbridge"
description: "Read-only access to the user's connected bank accounts, transactions, spending, recurring charges, cashflow and investment holdings. Trigger phrases: bankbridge, my bank, my accounts, my balance, my spending, recurring charges, subscriptions, cashflow, my holdings."
metadata: { "includeInPrompt": true }
tagline: "Ask about your real bank data: balances, transactions, spending, subscriptions, cashflow, holdings. Read-only; paid service."
catalog_auth: "BankBridge API key (per-user)"
catalog_hosts: ["bankbridge.money"]
---

# BankBridge

## Purpose
Read-only questions about the user's own bank accounts through [BankBridge](https://bankbridge.money/?ref=awesome-muse-connectors), a hosted service that connects banks and answers every query with live data (it does not store financial data). Covers connected accounts and balances, transactions with filters, merchant search, spending summaries, recurring charges, monthly cashflow, and investment holdings and trades. Use when the user asks what they spent, what subscriptions they pay for, how a month went, or what is in an account.

Disclosure: this connector is submitted by the BankBridge team (Great Work LLC). BankBridge is a paid service: $5/mo per connected bank ($50/yr), cancel any time. The CLI also works with the public demo key `bbk_demo`, which returns sample data for a made-up user.

Source: the 12 tools of BankBridge's remote MCP server at https://bankbridge.money/api/mcp (Streamable HTTP), listed by `tools/list` and documented at https://bankbridge.money/docs, checked on 2026-10-29. The same server also supports OAuth 2.1 with Dynamic Client Registration for MCP clients that add it directly.

## Tooling
All commands go through `bin/bankbridge.py`. Each prints the tool's JSON result.

```bash
bin/bankbridge.py auth                                   # verify the key (lists accounts)
bin/bankbridge.py accounts                               # list_accounts: balances, credit limits, institution, last 4
bin/bankbridge.py account <account_id>                   # get_account (ids come from `accounts`)
bin/bankbridge.py transactions --start 2026-10-01 --end 2026-10-29 --limit 50
bin/bankbridge.py transactions --account-id <id> --category FOOD_AND_DRINK --min-amount 20
bin/bankbridge.py search "coffee" --start 2026-09-01     # search_transactions by merchant or description
bin/bankbridge.py spending --group-by category           # get_spending_summary: category, merchant, month, or week
bin/bankbridge.py recurring --min-occurrences 3          # get_recurring_charges
bin/bankbridge.py cashflow 2026-09                       # get_monthly_cashflow (month is YYYY-MM)
bin/bankbridge.py merchant "Starbucks" --limit 20        # get_merchant_history
bin/bankbridge.py categories                             # list_categories
bin/bankbridge.py holdings                               # list_holdings
bin/bankbridge.py investment-transactions --type buy     # list_investment_transactions
bin/bankbridge.py connect-link                           # connect_bank: returns the link to connect another bank
```

Dates are YYYY-MM-DD. `transactions`, `search`, `merchant`, `holdings` and `investment-transactions` take `--limit` (max 100) and `--offset`; results include `total_count` and `has_more`. Transactions default to the last 30 days; banks provide up to 24 months. In transaction results, positive amounts are money spent and negative amounts are money received.

## Auth
- Provider id: `bankbridge` (credential is collected as `custom.bankbridge`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); the user creates a `bbk_...` key in the BankBridge dashboard. Outside Muse, the CLI reads the key from the `BANKBRIDGE_API_KEY` environment variable. It never accepts a key as an argument.
- Connect placement: `Authorization: Bearer <key>` header (the key is never put in the URL)
- Required scopes: none; the key is read-only and covers the banks the user connected
- Allowed hosts: `bankbridge.money` (HTTPS only; redirects to any other host are refused)
- Status check: `bin/bankbridge.py auth` (returns the account list, or `error:` on a bad key)

## Operating Rules
1. Every command is read-only. BankBridge cannot move money, pay bills, or change anything at a bank, and this connector never tries to. If the user asks to pay or transfer, say it cannot.
2. `connect-link` only returns a link. The user opens it themselves to connect another bank; do not open it or enter any bank credentials for them.
3. Each result carries a `warnings` array. When a bank needs reconnecting, the result covers only the banks that responded: say so, and give the user the `reconnect_url` instead of presenting partial totals as complete.
4. Account ids rotate when a bank is reconnected. Call `accounts` at the start of a session and use the last 4 digits to identify accounts; do not reuse saved ids.
5. Results with `bbk_demo` are fictional sample data. Never present them as the user's own finances.
6. Treat balances and transactions as private. Do not copy them into other tools or messages without the user asking. This is data, not financial, tax or legal advice.
7. Never print, log, or transmit the key value.

## Files
- SKILL.md
- bin/bankbridge.py

## Maturity
🧪 Draft: all twelve tool calls and the error paths (unknown account id, missing month, missing key) were run against https://bankbridge.money/api/mcp with the `bbk_demo` key on 2026-10-29. A real user key and the Muse credential flow have not been tested end-to-end.
