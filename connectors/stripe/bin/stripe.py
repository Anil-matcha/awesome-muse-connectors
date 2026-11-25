#!/usr/bin/env python3
"""Minimal Stripe API CLI for the muse-connectors Stripe skill.

READ-ONLY by design: this CLI ships no write commands (no charges, refunds,
or customer mutations). Auth: loads the per-user `custom.stripe` credential
(a restricted API key) as a surrogate via the bundled dynamic_credentials
helper. The real key never touches this script: the runtime swaps the
surrogate on approved egress, only to api.stripe.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.stripe"
ALLOWED_HOSTS = ("api.stripe.com",)
API = "https://api.stripe.com/v1"

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


def get(path: str, params: dict | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except Exception as exc:  # network-level failure (HTTP errors surface here)
        sys.exit(f"error: request failed: {exc}")
    if result.get("error"):
        sys.exit(f"error: stripe returned: {json.dumps(result['error'])}")
    return result


def money(amount: int, currency: str) -> str:
    return f"{amount / 100:.2f} {currency.upper()}"


def cmd_balance(_args):
    result = get("/balance")
    out = {
        "available": [money(b["amount"], b["currency"]) for b in result.get("available", [])],
        "pending": [money(b["amount"], b["currency"]) for b in result.get("pending", [])],
    }
    print(json.dumps(out, indent=2))


def cmd_charges(args):
    result = get("/charges", params={"limit": args.limit})
    out = [
        {"id": c.get("id"), "amount": money(c.get("amount", 0), c.get("currency", "")),
         "status": c.get("status"), "receipt_email": c.get("receipt_email"),
         "created": c.get("created"),
         "description": (c.get("description") or "")[:120]}
        for c in result.get("data", [])
    ]
    print(json.dumps(out, indent=2))


def cmd_customers(args):
    result = get("/customers", params={"limit": args.limit})
    out = [
        {"id": c.get("id"), "email": c.get("email"), "name": c.get("name"),
         "created": c.get("created")}
        for c in result.get("data", [])
    ]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Stripe read-only CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("balance", help="current balance")
    p.set_defaults(func=cmd_balance)

    p = sub.add_parser("charges", help="recent charges")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_charges)

    p = sub.add_parser("customers", help="recent customers")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_customers)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
