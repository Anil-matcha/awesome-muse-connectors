#!/usr/bin/env python3
"""YNAB API CLI. Uses the user-connected custom.ynab credential via authd surrogates.

Amounts come back in milliunits (1000 = $1.00); this CLI converts to dollars.

Subcommands:
  auth                       Verify the stored credential answers (status check)
  plans                      List budgets (plans)
  accounts [--plan ID]       Accounts with type, balance, cleared balance
  categories [--plan ID]     Category groups + categories with goals
  month [--plan ID] [YYYY-MM] Month detail: budgeted, activity, balances (default: current)
  transactions [--plan ID] [--since YYYY-MM-DD] [--type uncategorized|unapproved] [--limit N]

Reads only. Writes are deliberately NOT in this CLI: any YNAB write must
follow the guarded-write pattern in SKILL.md (dry-run, snapshot-before-write,
post-write verify, audit log, Ready-to-Assign and future-month guards).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import (  # noqa: E402
    add_surrogate_to_request,
    read_json_response,
)

BASE = "https://api.ynab.com/v1"
CREDENTIAL = "custom.ynab"
ALLOWED = ["api.ynab.com"]


def api(path: str) -> dict:
    req = urllib.request.Request(BASE + path, method="GET")
    add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=ALLOWED)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = "<unreadable>"
        raise SystemExit(f"YNAB API HTTP {exc.code}: {body[:500]}")


def dollars(milli: int | None) -> float | None:
    return None if milli is None else round(milli / 1000, 2)


def cmd_auth(_args):
    data = api("/budgets")
    budgets = [b["name"] for b in data["data"]["budgets"]]
    print(json.dumps({"ok": True, "budgets": budgets}))


def cmd_plans(_args):
    data = api("/budgets")
    for b in data["data"]["budgets"]:
        print(f"{b['id']}  {b['name']}  first={b.get('first_month')} last={b.get('last_month')}")


def cmd_accounts(args):
    plan = args.plan or "last-used"
    data = api(f"/budgets/{plan}/accounts")
    for a in data["data"]["accounts"]:
        if a.get("deleted"):
            continue
        print(f"{a['id']}  {a.get('name')}  type={a.get('type')}  "
              f"balance={dollars(a.get('balance'))} cleared={dollars(a.get('cleared_balance'))} "
              f"on_budget={a.get('on_budget')} closed={a.get('closed')}")


def cmd_categories(args):
    plan = args.plan or "last-used"
    data = api(f"/budgets/{plan}/categories")
    for group in data["data"]["category_groups"]:
        if group.get("deleted"):
            continue
        print(f"\n== {group['name']} ==")
        for c in group["categories"]:
            if c.get("deleted"):
                continue
            goal = c.get("goal_target")
            gtype = c.get("goal_type") or "-"
            print(f"  {c['name']}  goal={goal and dollars(goal)} type={gtype} hidden={c.get('hidden')}")


def cmd_month(args):
    plan = args.plan or "last-used"
    m = args.month or "current"
    data = api(f"/budgets/{plan}/months/{m}")
    mo = data["data"]["month"]
    print(f"Month {mo['month']}: income={dollars(mo.get('income'))} budgeted={dollars(mo.get('budgeted'))} "
          f"activity={dollars(mo.get('activity'))} to_be_budgeted={dollars(mo.get('to_be_budgeted'))} "
          f"age_of_money={mo.get('age_of_money')}")
    for c in mo["categories"]:
        if c.get("deleted") or c.get("hidden"):
            continue
        print(f"  {c['name']}: budgeted={dollars(c.get('budgeted'))} activity={dollars(c.get('activity'))} "
              f"balance={dollars(c.get('balance'))} goal_target={c.get('goal_target') and dollars(c['goal_target'])}")


def cmd_transactions(args):
    plan = args.plan or "last-used"
    params = []
    if args.since:
        params.append(f"since_date={args.since}")
    if args.type:
        params.append(f"type={args.type}")
    q = ("?" + "&".join(params)) if params else ""
    data = api(f"/budgets/{plan}/transactions{q}")
    txns = data["data"]["transactions"]
    for t in txns[: args.limit]:
        print(f"{t['date']}  {dollars(t['amount']):>9}  {t.get('payee_name') or t.get('payee_id','?')}  "
              f"[{t.get('category_name') or 'uncategorized'}] approved={t.get('approved')} memo={t.get('memo') or ''}")


def main():
    ap = argparse.ArgumentParser(prog="ynab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth")
    sub.add_parser("plans")
    p = sub.add_parser("accounts"); p.add_argument("--plan")
    p = sub.add_parser("categories"); p.add_argument("--plan")
    p = sub.add_parser("month"); p.add_argument("--plan"); p.add_argument("month", nargs="?")
    p = sub.add_parser("transactions"); p.add_argument("--plan"); p.add_argument("--since"); p.add_argument("--type"); p.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    {"auth": cmd_auth, "plans": cmd_plans, "accounts": cmd_accounts, "categories": cmd_categories, "month": cmd_month, "transactions": cmd_transactions}[args.cmd](args)


if __name__ == "__main__":
    main()
