#!/usr/bin/env python3
"""Minimal Printful API CLI for the muse-connectors printful skill.

Auth: `Authorization: Bearer <token>`. Account-level tokens also need the
`X-PF-Store-Id` header; pass `--store-id` for that (store-scoped tokens do
not need it). Loads the per-user `custom.printful` credential as a
surrogate via the bundled dynamic_credentials helper. The real token never
touches this script: the runtime swaps the surrogate on approved egress,
only to api.printful.com.

`order-create` submits real fulfillment and spends real money: it is
confirmation-gated, never automatic.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.printful"
ALLOWED_HOSTS = ("api.printful.com",)
API = "https://api.printful.com"

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
         payload: dict | None = None) -> object:
    url = API + path
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
    if getattr(args, "store_id", None):
        req.add_header("X-PF-Store-Id", args.store_id)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", {}).get("message", str(exc)) \
                if isinstance(body.get("error"), dict) else body.get("error", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: printful returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def unwrap(result: object) -> object:
    # Printful wraps payloads in {"code", "result", ...}.
    if isinstance(result, dict) and "result" in result:
        return result["result"]
    return result


def load_json(text: str) -> dict:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --json is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        sys.exit("error: --json must be a JSON object")
    return payload


def cmd_auth(args):
    result = unwrap(call("GET", "/store/products", args,
                         params={"limit": 1}))
    count = len(result) if isinstance(result, list) else 0
    print(json.dumps({"ok": True, "store_products": count}, indent=2))


def cmd_products(args):
    result = unwrap(call("GET", "/store/products", args,
                         params={"limit": args.limit, "offset": args.offset}))
    products = [
        {"id": p.get("id"), "external_id": p.get("external_id"),
         "name": p.get("name"), "variants": p.get("variants"),
         "thumbnail_url": p.get("thumbnail_url")}
        for p in (result if isinstance(result, list) else [])
    ]
    print(json.dumps(products, indent=2))


def cmd_orders(args):
    params = {"limit": args.limit, "offset": args.offset}
    if args.status:
        params["status"] = args.status
    result = unwrap(call("GET", "/orders", args, params=params))
    orders = [
        {"id": o.get("id"), "external_id": o.get("external_id"),
         "status": o.get("status"), "created": o.get("created"),
         "recipient": (o.get("recipient") or {}).get("name"),
         "costs": o.get("costs")}
        for o in (result if isinstance(result, list) else [])
    ]
    print(json.dumps(orders, indent=2))


def cmd_order_create(args):
    result = unwrap(call("POST", "/orders", args,
                         payload=load_json(args.json)))
    order = result if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "id": order.get("id"),
                      "external_id": order.get("external_id"),
                      "status": order.get("status"),
                      "costs": order.get("costs")}, indent=2))


def cmd_catalog_product(args):
    result = unwrap(call("GET", f"/products/{args.id}", args))
    product = result if isinstance(result, dict) else {}
    variants = product.get("variants", [])
    print(json.dumps({
        "id": product.get("id"), "title": product.get("title"),
        "type": product.get("type"), "type_name": product.get("type_name"),
        "variant_count": len(variants) if isinstance(variants, list) else 0,
        "variants": variants,
    }, indent=2))


def cmd_mockup_create(args):
    result = unwrap(call("POST",
                         f"/mockup-generator/create-task/{args.product_id}",
                         args, payload=load_json(args.json)))
    task = result if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "task_key": task.get("task_key"),
                      "status": task.get("status")}, indent=2))


def add_store(p):
    p.add_argument("--store-id", default=None,
                   help="required for account-level tokens (X-PF-Store-Id)")


def main():
    parser = argparse.ArgumentParser(
        description="Printful API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the token")
    add_store(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("products", help="list synced store products")
    add_store(p)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--offset", type=int, default=0)
    p.set_defaults(func=cmd_products)

    p = sub.add_parser("orders", help="list orders")
    add_store(p)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--status", default=None)
    p.set_defaults(func=cmd_orders)

    p = sub.add_parser("order-create",
                       help="submit an order for fulfillment (confirm first; spends money)")
    add_store(p)
    p.add_argument("--json", required=True,
                   help="order payload as a JSON object string")
    p.set_defaults(func=cmd_order_create)

    p = sub.add_parser("catalog-product", help="show a catalog product and its variants")
    add_store(p)
    p.add_argument("--id", required=True, help="catalog product ID")
    p.set_defaults(func=cmd_catalog_product)

    p = sub.add_parser("mockup-create",
                       help="start a mockup-generator task for a catalog product")
    add_store(p)
    p.add_argument("--product-id", required=True,
                   help="catalog product ID")
    p.add_argument("--json", required=True,
                   help="mockup task payload as a JSON object string")
    p.set_defaults(func=cmd_mockup_create)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
