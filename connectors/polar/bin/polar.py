#!/usr/bin/env python3
"""Minimal Polar API CLI for the muse-connectors polar skill.

Auth: `Authorization: Bearer <token>` with an Organization Access Token
(prefixed `polar_oat_`, scoped in the org dashboard). Loads the per-user
`custom.polar` credential as a surrogate via the bundled
dynamic_credentials helper. The real token never touches this script: the
runtime swaps the surrogate on approved egress, only to api.polar.sh (or
sandbox-api.polar.sh with --sandbox).

Checkouts and refunds are confirmation-gated (they move money).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.polar"
ALLOWED_HOSTS = ("api.polar.sh", "sandbox-api.polar.sh")
API = "https://api.polar.sh/v1"
SANDBOX_API = "https://sandbox-api.polar.sh/v1"

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


def call(method: str, path: str, args, params: dict | None = None,
         payload: dict | None = None) -> dict:
    base = SANDBOX_API if args.sandbox else API
    url = base + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME,
                                 allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            retry = exc.headers.get("Retry-After")
            hint = f"; retry after {retry}s" if retry else ""
            sys.exit(f"error: polar rate-limited (HTTP 429){hint}; "
                     "back off and try again")
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("detail", body.get("message", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: polar returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def items_of(result: dict) -> list:
    if not isinstance(result, dict):
        return []
    items = result.get("items", result.get("data", []))
    return items if isinstance(items, list) else []


def load_json(text: str) -> dict:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --json is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        sys.exit("error: --json must be a JSON object")
    return payload


def cmd_auth(args):
    result = call("GET", "/orders", args, params={"limit": 1})
    print(json.dumps({"ok": True, "orders": len(items_of(result))}, indent=2))


def cmd_orders(args):
    params = {"limit": args.limit}
    if args.organization_id:
        params["organization_id"] = args.organization_id
    result = call("GET", "/orders", args, params=params)
    print(json.dumps(items_of(result), indent=2))


def cmd_subscriptions(args):
    params = {"limit": args.limit}
    if args.organization_id:
        params["organization_id"] = args.organization_id
    result = call("GET", "/subscriptions", args, params=params)
    print(json.dumps(items_of(result), indent=2))


def cmd_products(args):
    params = {"limit": args.limit}
    if args.organization_id:
        params["organization_id"] = args.organization_id
    result = call("GET", "/products", args, params=params)
    print(json.dumps(items_of(result), indent=2))


def cmd_customers(args):
    params = {"limit": args.limit}
    if args.organization_id:
        params["organization_id"] = args.organization_id
    result = call("GET", "/customers", args, params=params)
    print(json.dumps(items_of(result), indent=2))


def cmd_checkout_create(args):
    result = call("POST", "/checkouts", args, payload=load_json(args.json))
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "url": result.get("url")}, indent=2))


def cmd_refund_create(args):
    result = call("POST", "/refunds", args, payload=load_json(args.json))
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "status": result.get("status")}, indent=2))


def add_sandbox(p):
    p.add_argument("--sandbox", action="store_true",
                   help="use the Polar sandbox API instead of production")


def add_org(p):
    p.add_argument("--organization-id", default=None)


def main():
    parser = argparse.ArgumentParser(description="Polar API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the access token")
    add_sandbox(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("orders", help="list orders")
    add_sandbox(p); add_org(p)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_orders)

    p = sub.add_parser("subscriptions", help="list subscriptions")
    add_sandbox(p); add_org(p)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_subscriptions)

    p = sub.add_parser("products", help="list products")
    add_sandbox(p); add_org(p)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_products)

    p = sub.add_parser("customers", help="list customers")
    add_sandbox(p); add_org(p)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_customers)

    p = sub.add_parser("checkout-create",
                       help="create a checkout session (confirm first)")
    add_sandbox(p)
    p.add_argument("--json", required=True,
                   help="checkout payload as a JSON object string")
    p.set_defaults(func=cmd_checkout_create)

    p = sub.add_parser("refund-create",
                       help="issue a refund (confirm first)")
    add_sandbox(p)
    p.add_argument("--json", required=True,
                   help="refund payload as a JSON object string")
    p.set_defaults(func=cmd_refund_create)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
