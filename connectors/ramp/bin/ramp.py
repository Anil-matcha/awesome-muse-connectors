#!/usr/bin/env python3
"""Read-only Ramp corporate-spend API CLI for the muse-connectors ramp skill.

Auth: loads the per-user `custom.ramp` credential as a surrogate via the
bundled dynamic_credentials helper. Ramp uses OAuth 2.0 client credentials:
a client id/secret minted in the Ramp dashboard is exchanged at
POST /developer/v1/token for a short-lived Bearer token, and the runtime
hands this script a fresh one. The real credential never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.ramp.com.

Safety: READ-ONLY by design. This CLI wires only GET endpoints. There are no
spend, card-issuance, payment, reimbursement, or bill-pay commands, and none
will be added without an explicit user request plus a security review.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.ramp"
ALLOWED_HOSTS = ("api.ramp.com",)
BASE = "https://api.ramp.com/developer/v1"
CONNECT_GUIDANCE = (
    "not connected: mint a Ramp API client (dashboard > Settings > Developer), "
    "enable read-only scopes (transactions:read, cards:read, users:read), and "
    "collect the client credentials via the secure credential flow "
    "(credentials.request_api_access) as `custom.ramp`, then retry."
)

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        add_surrogate_to_request,
        read_json_response,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def call(method: str, path: str) -> dict:
    url = BASE + path
    req = urllib.request.Request(
        url, headers={"Accept": "application/json"}, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        if "missing" in str(exc) or "surrogate" in str(exc):
            sys.exit(CONNECT_GUIDANCE)
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            msg = body[:500]
        except Exception:
            msg = str(exc)
        sys.exit(f"error: ramp returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def page_params(limit: int) -> str:
    return urllib.parse.urlencode({"page_size": limit})


def cmd_auth(args):
    result = call("GET", f"/users?{page_params(1)}")
    print(json.dumps({"ok": True, "base": BASE,
                      "note": "credential accepted"}, indent=2))


def cmd_transactions(args):
    params = {"page_size": args.limit}
    if args.from_date:
        params["from_date"] = args.from_date
    if args.to_date:
        params["to_date"] = args.to_date
    result = call("GET", f"/transactions?{urllib.parse.urlencode(params)}")
    txs = [{"id": t.get("id"), "amount": t.get("amount"),
            "merchant_name": t.get("merchant_name"),
            "state": t.get("state"),
            "transaction_date": t.get("transaction_date"),
            "card_id": t.get("card_id"), "user_id": t.get("user_id")}
           for t in result.get("data", [])]
    print(json.dumps(txs, indent=2))


def cmd_transaction_get(args):
    result = call("GET", f"/transactions/{args.transaction_id}")
    t = result.get("data", result)
    print(json.dumps({"id": t.get("id"), "amount": t.get("amount"),
                      "merchant_name": t.get("merchant_name"),
                      "state": t.get("state"),
                      "transaction_date": t.get("transaction_date"),
                      "card_id": t.get("card_id"), "user_id": t.get("user_id"),
                      "receipts": t.get("receipts")}, indent=2))


def cmd_cards(args):
    result = call("GET", f"/cards?{page_params(args.limit)}")
    cards = [{"id": c.get("id"), "display_name": c.get("display_name"),
              "state": c.get("state"),
              "cardholder_id": c.get("cardholder_id"),
              "card_program_id": c.get("card_program_id")}
             for c in result.get("data", [])]
    print(json.dumps(cards, indent=2))


def cmd_card_limits(args):
    result = call("GET", f"/cards/{args.card_id}")
    c = result.get("data", result)
    print(json.dumps({"id": c.get("id"),
                      "display_name": c.get("display_name"),
                      "state": c.get("state"),
                      "spending_restrictions": c.get("spending_restrictions")},
                     indent=2))


def cmd_users(args):
    result = call("GET", f"/users?{page_params(args.limit)}")
    users = [{"id": u.get("id"), "first_name": u.get("first_name"),
              "last_name": u.get("last_name"), "email": u.get("email"),
              "status": u.get("status"),
              "department_id": u.get("department_id"),
              "location_id": u.get("location_id")}
             for u in result.get("data", [])]
    print(json.dumps(users, indent=2))


def cmd_departments(args):
    result = call("GET", f"/departments?{page_params(args.limit)}")
    depts = [{"id": d.get("id"), "name": d.get("name"),
              "parent_id": d.get("parent_id")}
             for d in result.get("data", [])]
    print(json.dumps(depts, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Ramp corporate-spend API CLI, read-only (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the credential")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("transactions", help="list transactions")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--from-date", default=None,
                   help="ISO 8601 start, e.g. 2026-09-01T00:00:00Z")
    p.add_argument("--to-date", default=None,
                   help="ISO 8601 end, e.g. 2026-09-30T23:59:59Z")
    p.set_defaults(func=cmd_transactions)

    p = sub.add_parser("transaction-get", help="retrieve one transaction")
    p.add_argument("--transaction-id", required=True)
    p.set_defaults(func=cmd_transaction_get)

    p = sub.add_parser("cards", help="list cards")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_cards)

    p = sub.add_parser("card-limits",
                       help="show a card's spending restrictions")
    p.add_argument("--card-id", required=True)
    p.set_defaults(func=cmd_card_limits)

    p = sub.add_parser("users", help="list users")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_users)

    p = sub.add_parser("departments", help="list departments")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_departments)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
