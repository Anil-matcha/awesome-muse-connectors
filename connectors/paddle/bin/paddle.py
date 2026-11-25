#!/usr/bin/env python3
"""Minimal Paddle API CLI for the muse-connectors Paddle skill.

Read-only: transactions and customers. Auth: loads the per-user
`custom.paddle` credential as a surrogate via the bundled
dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api.paddle.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.paddle"
ALLOWED_HOSTS = ("api.paddle.com",)
API = "https://api.paddle.com"

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


def call(path: str, params: dict | None = None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={})
    try:
        add_surrogate_to_request(
            req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS
        )
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        sys.exit(f"error: HTTP {exc.code}: {body[:300]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = call("/event-types")
    if not isinstance(result, dict) or not isinstance(result.get("data"), list):
        sys.exit(f"error: paddle auth check failed: {json.dumps(result)[:300]}")
    print(json.dumps({"ok": True}, indent=2))


def per_page(limit: int) -> int:
    return max(1, min(limit, 200))


def cmd_transactions(args):
    result = call("/transactions", params={"per_page": per_page(args.limit)})
    items = result.get("data", []) if isinstance(result, dict) else []
    out = [
        {"id": t.get("id"), "status": t.get("status"),
         "totals": (t.get("details") or {}).get("totals")}
        for t in items
    ]
    print(json.dumps(out, indent=2))


def cmd_customers(args):
    result = call("/customers", params={"per_page": per_page(args.limit)})
    items = result.get("data", []) if isinstance(result, dict) else []
    out = [{"email": c.get("email"), "name": c.get("name")} for c in items]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Paddle API CLI (muse-connectors, read-only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection (via event-types)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("transactions", help="recent transactions")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_transactions)

    p = sub.add_parser("customers", help="customers")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_customers)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
