#!/usr/bin/env python3
"""Minimal Lemon Squeezy API CLI for the muse-connectors lemon-squeezy skill.

Auth: `Authorization: Bearer <key>` plus `Accept: application/vnd.api+json`.
Loads the per-user `custom.lemon-squeezy` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.lemonsqueezy.com.

Responses are JSON:API (nested data.attributes); parsed defensively.
Checkout creation is confirmation-gated (creates a real payment link).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.lemon-squeezy"
ALLOWED_HOSTS = ("api.lemonsqueezy.com",)
API = "https://api.lemonsqueezy.com/v1"

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


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {"Accept": "application/vnd.api+json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/vnd.api+json"
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
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            errors = body.get("errors", [])
            msg = "; ".join(e.get("detail", str(e)) for e in errors) or str(exc)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: lemon squeezy returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def flatten(items: list) -> list:
    """Defensively unwrap JSON:API `data` (id + nested attributes)."""
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            out.append(item)
            continue
        attrs = item.get("attributes", {})
        row = {"id": item.get("id"), "type": item.get("type")}
        if isinstance(attrs, dict):
            row.update(attrs)
        out.append(row)
    return out


def get_data(result: dict) -> list:
    if not isinstance(result, dict):
        return []
    data = result.get("data", [])
    return data if isinstance(data, list) else [data]


def cmd_auth(_args):
    result = call("GET", "/orders", params={"page[size]": 1})
    print(json.dumps({"ok": True, "orders": len(get_data(result))}, indent=2))


def cmd_orders(args):
    params = {"page[size]": args.limit}
    if args.store_id:
        params["filter[store_id]"] = args.store_id
    if args.status:
        params["filter[status]"] = args.status
    result = call("GET", "/orders", params=params)
    print(json.dumps(flatten(get_data(result)), indent=2))


def cmd_subscriptions(args):
    params = {"page[size]": args.limit}
    if args.store_id:
        params["filter[store_id]"] = args.store_id
    if args.status:
        params["filter[status]"] = args.status
    result = call("GET", "/subscriptions", params=params)
    print(json.dumps(flatten(get_data(result)), indent=2))


def cmd_customers(args):
    params = {"page[size]": args.limit}
    if args.store_id:
        params["filter[store_id]"] = args.store_id
    if args.email:
        params["filter[email]"] = args.email
    result = call("GET", "/customers", params=params)
    print(json.dumps(flatten(get_data(result)), indent=2))


def cmd_products(args):
    params = {"page[size]": args.limit}
    if args.store_id:
        params["filter[store_id]"] = args.store_id
    result = call("GET", "/products", params=params)
    print(json.dumps(flatten(get_data(result)), indent=2))


def cmd_checkout_create(args):
    try:
        payload = json.loads(args.json)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --json is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        sys.exit("error: --json must be a JSON object")
    result = call("POST", "/checkouts", payload=payload)
    created = get_data(result)
    row = created[0] if created else {}
    attrs = row.get("attributes", {}) if isinstance(row, dict) else {}
    print(json.dumps({"ok": True, "id": row.get("id") if isinstance(row, dict) else None,
                      "url": attrs.get("url") if isinstance(attrs, dict) else None},
                     indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Lemon Squeezy API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("orders", help="list orders")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--store-id", default=None)
    p.add_argument("--status", default=None)
    p.set_defaults(func=cmd_orders)

    p = sub.add_parser("subscriptions", help="list subscriptions")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--store-id", default=None)
    p.add_argument("--status", default=None)
    p.set_defaults(func=cmd_subscriptions)

    p = sub.add_parser("customers", help="list customers")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--store-id", default=None)
    p.add_argument("--email", default=None)
    p.set_defaults(func=cmd_customers)

    p = sub.add_parser("products", help="list products")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--store-id", default=None)
    p.set_defaults(func=cmd_products)

    p = sub.add_parser("checkout-create",
                       help="create a checkout link (confirm first)")
    p.add_argument("--json", required=True,
                   help="JSON:API checkout payload as a JSON object string")
    p.set_defaults(func=cmd_checkout_create)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
