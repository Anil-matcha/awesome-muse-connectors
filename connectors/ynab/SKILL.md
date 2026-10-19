---
name: "ynab"
description: "Read and maintain YNAB budgets: plans, accounts, categories with goal targets, month funding/activity, transactions — all in dollars. Trigger phrases: ynab, budget, my budget, spending, ready to assign."
metadata: { "includeInPrompt": true }
tagline: "Read YNAB budgets in dollars — plans, accounts, categories with goal targets, month funding and activity, transactions with filters — plus the guarded-write pattern (dry-run, snapshot, verify, audit log) for any change."
catalog_auth: "OAuth 2.0 via the secure credential flow"
catalog_hosts: ["api.ynab.com"]
---

# YNAB

## Purpose
Read the user's YNAB (You Need A Budget) budgets through the public YNAB API: budget plans, accounts with balances, category groups with goal targets and goal types, month detail (income, budgeted, activity, Ready to Assign, age of money, per-category goal targets), and transactions with since-date and uncategorized/unapproved filters. All amounts are converted from the API's milliunits to dollars by the CLI. Use when the user mentions YNAB, their budget, category funding, or spending.

Source: YNAB API documentation (api.ynab.com), checked 2026-10-19.

## Tooling
All commands go through `bin/ynab.py`:

```bash
bin/ynab.py auth                                          # status check: verify the credential answers
bin/ynab.py plans                                         # list budgets
bin/ynab.py accounts [--plan last-used]                   # accounts: type, balance, cleared balance
bin/ynab.py categories [--plan last-used]                 # category groups + categories with goal targets
bin/ynab.py month [--plan last-used] [YYYY-MM|current]    # month funding, activity, balances
bin/ynab.py transactions [--plan last-used] [--since YYYY-MM-DD] [--type uncategorized|unapproved] [--limit N]
```

`--plan` accepts a budget ID or `last-used` (the default). This CLI is read-only by design — see Operating Rules for how writes are handled.

## Auth
- Provider id: `ynab` (credential is collected as `custom.ynab`)
- Collection: OAuth 2.0 via the secure credential flow (`credentials.request_api_access`); register an app under YNAB Settings > Developer > New Application. A paid YNAB subscription is required.
- Required scopes: the default read/write scope of a registered YNAB app (this connector only reads through the CLI).
- Allowed hosts: `api.ynab.com`
- Status check: `bin/ynab.py auth` (must return `"ok": true`)

## Operating Rules
1. The YNAB API is bookkeeping only. It can never move money, make transfers, or touch bank accounts. Say this plainly if the user asks to "pay" or "transfer" through it.
2. Reads need no confirmation. Amounts: the API works in milliunits; this CLI already converts reads to dollars — never present raw milliunits to the user.
3. **Writes do not ship in this CLI, deliberately.** The previous catalog version's direct `transaction-create` had no dry-run, snapshot, audit trail, or idempotency, so a lost response plus a retry could duplicate a transaction. In the production setup this connector comes from, every YNAB write goes through a separate guarded writer that enforces, in order:
   - **Dry-run by default** — the write only executes with an explicit apply flag after the plan is shown.
   - **Fresh-pull requirement** — refuse to write from data older than one hour.
   - **Snapshot-before-write** — persist the affected month/accounts state first, so any write can be rolled back.
   - **Post-write verification** — re-read and confirm the change landed as planned.
   - **Audit log** — append every executed write (what, when, before/after) to a JSONL audit file.
   - **Month-health guards** — Ready to Assign must never go negative in the written month, and no future month may carry a negative category balance (a negative future balance is always an assignment error and silently docks the next month's Ready to Assign). Cap any single run (the production cap is $25k).
   - **Never-write classes** — Fresh Start, account create/delete, category create/delete/move, goal-shape changes, and writes to past months are out of scope for automation entirely.
   Any connector that adds YNAB writes should implement the same pattern and still confirm amount, account, payee, and date with the user before recording, unless standing permission exists.
4. A 401/403 is a question about the request before it is a question about the credential — confirm the surrogate was attached. Never print, log, or persist the raw token; the CLI only ever handles surrogates.

## Files
- SKILL.md
- bin/ynab.py

## Maturity
✅ Live — this is the production version from a running Muse setup: reads run daily against a live budget (month reconciliation, category-goal checks, transaction logging verification), and the guarded-write pattern above is the one its companion writer enforces. Live-tested 2026-10-19.
