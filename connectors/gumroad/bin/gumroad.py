#!/usr/bin/env python3
"""Minimal Gumroad API CLI for the muse-connectors Gumroad skill.

Read-only: user, products, sales. Auth: loads the per-user
`custom.gumroad` credential as a surrogate via the bundled
dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api.gumroad.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.gumroad"
ALLOWED_HOSTS = ("api.gumroad.com",)
API = "https://api.gumroad.com/v2"

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


def require_success(result, what: str) -> dict:
    if not isinstance(result, dict) or not result.get("success"):
        sys.exit(f"error: gumroad {what} failed: {json.dumps(result)[:300]}")
    return result


def cmd_auth(_args):
    result = require_success(call("/user"), "auth")
    user = result.get("user", {})
    print(json.dumps({"ok": True, "name": user.get("name"), "email": user.get("email")}, indent=2))


def cmd_products(_args):
    result = require_success(call("/products"), "products")
    out = [
        {"name": p.get("name"), "price_usd": (p.get("price") or 0) / 100}
        for p in result.get("products", [])
    ]
    print(json.dumps(out, indent=2))


def cmd_sales(args):
    result = require_success(call("/sales"), "sales")
    out = [
        {"product_name": s.get("product_name"),
         "price_usd": (s.get("price") or 0) / 100,
         "email": s.get("email")}
        for s in result.get("sales", [])
    ]
    print(json.dumps(out[: args.limit], indent=2))


def main():
    parser = argparse.ArgumentParser(description="Gumroad API CLI (muse-connectors, read-only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("products", help="list products")
    p.set_defaults(func=cmd_products)

    p = sub.add_parser("sales", help="recent sales")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_sales)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
