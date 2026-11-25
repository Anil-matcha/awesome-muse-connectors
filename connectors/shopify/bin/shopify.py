#!/usr/bin/env python3
"""Minimal Shopify Admin API CLI for the muse-connectors Shopify skill.

Reads: shop info, open orders, products, customers.
Writes (exact --confirm required on every call): product-create (new
product with one variant) and discount-create (price rule + discount
code). No order or customer writes exist in this CLI, by design.

Auth: loads the per-user `custom.shopify` credential as a surrogate via
the bundled dynamic_credentials helper. The real token never touches
this script: the runtime swaps the surrogate on approved egress, only to
the store's own .myshopify.com host (placement: custom header
X-Shopify-Access-Token).

HONESTY NOTE: endpoint paths and body shapes are taken from Shopify's
public Admin API docs and have not been verified in a live flow. The
API version below is the latest stable per secondary evidence (2026-07
as of ~September 2026); Shopify retires old versions, so if calls fail
with a version error, check the current stable version.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.shopify"
# HONESTY NOTE: secondary evidence (Pipedream pin, community skill checks
# from mid/late 2026) points to 2026-07 as the latest stable Admin API
# version as of ~September 2026; verify against Shopify's versioning docs
# if calls fail.
API_VERSION = "2026-07"

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


def normalize_shop(shop: str) -> str:
    """Accept 'mystore', 'mystore.myshopify.com', or a full URL; return the host."""
    host = shop.strip()
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/")[0].strip().rstrip("/").lower()
    if not host.endswith(".myshopify.com"):
        host += ".myshopify.com"
    return host


def call(method: str, path: str, shop_host: str, params: dict | None = None,
         payload: dict | None = None):
    url = f"https://{shop_host}/admin/api/{API_VERSION}" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method=method)
    try:
        add_surrogate_to_request(
            req, CREDENTIAL_NAME, allowed_hosts=(shop_host,)
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


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def cmd_auth(args):
    shop_host = normalize_shop(args.shop)
    result = call("GET", "/shop.json", shop_host)
    shop = result.get("shop", {}) if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "name": shop.get("name"), "domain": shop.get("domain")}, indent=2))


def cmd_orders(args):
    shop_host = normalize_shop(args.shop)
    result = call("GET", "/orders.json", shop_host, params={"status": "open", "limit": args.limit})
    orders = result.get("orders", []) if isinstance(result, dict) else []
    out = [
        {"name": o.get("name"), "total_price": o.get("total_price"),
         "financial_status": o.get("financial_status")}
        for o in orders
    ]
    print(json.dumps(out, indent=2))


def cmd_products(args):
    shop_host = normalize_shop(args.shop)
    result = call("GET", "/products.json", shop_host, params={"limit": args.limit})
    products = result.get("products", []) if isinstance(result, dict) else []
    out = [{"title": p.get("title"), "status": p.get("status")} for p in products]
    print(json.dumps(out, indent=2))


def cmd_customers(args):
    shop_host = normalize_shop(args.shop)
    result = call("GET", "/customers.json", shop_host, params={"limit": args.limit})
    customers = result.get("customers", []) if isinstance(result, dict) else []
    out = [
        {"first_name": c.get("first_name"), "last_name": c.get("last_name"),
         "email": c.get("email")}
        for c in customers
    ]
    print(json.dumps(out, indent=2))


def cmd_product_create(args):
    shop_host = normalize_shop(args.shop)
    expected = f'create product "{args.title}" at price {args.price}'
    need_confirm(
        args, expected,
        f"creating a new DRAFT product titled {args.title!r} in the "
        f"{shop_host} store (hidden from shoppers until activated).")
    variant = {"price": args.price}
    if args.sku:
        variant["sku"] = args.sku
    product = {"title": args.title, "status": "draft",
               "variants": [variant]}
    if args.body_html:
        product["body_html"] = args.body_html
    result = call("POST", "/products.json", shop_host,
                  payload={"product": product})
    p = result.get("product", {}) if isinstance(result, dict) else {}
    v = (p.get("variants") or [{}])[0]
    print(json.dumps({"ok": True, "product_id": p.get("id"),
                      "title": p.get("title"), "status": p.get("status"),
                      "variant_price": v.get("price"),
                      "variant_sku": v.get("sku")}, indent=2))


def cmd_discount_create(args):
    shop_host = normalize_shop(args.shop)
    if (args.percent is None) == (args.amount is None):
        sys.exit("error: pass exactly one of --percent or --amount")
    if args.percent is not None:
        value_type, value = "percentage", f"-{args.percent}"
    else:
        value_type, value = "fixed_amount", f"-{args.amount}"
    expected = (f'create discount "{args.title}" '
                f'({value_type} {value}) with code {args.code}')
    need_confirm(
        args, expected,
        f"creating a discount price rule {args.title!r} ({value_type} "
        f"{value}) in the {shop_host} store with redeemable code "
        f"{args.code!r}.")
    price_rule = {
        "title": args.title,
        "target_type": "line_item",
        "target_selection": "all",
        "allocation_method": "across",
        "value_type": value_type,
        "value": value,
        "customer_selection": "all",
        "starts_at": datetime.now(timezone.utc).isoformat(),
    }
    if args.ends_at:
        price_rule["ends_at"] = args.ends_at
    if args.usage_limit is not None:
        price_rule["usage_limit"] = args.usage_limit
    rule_result = call("POST", "/price_rules.json", shop_host,
                       payload={"price_rule": price_rule})
    rule = (rule_result.get("price_rule") or {}
            if isinstance(rule_result, dict) else {})
    rule_id = rule.get("id")
    if not rule_id:
        sys.exit("error: price rule created but no ID was returned")
    code_result = call("POST", f"/price_rules/{rule_id}/discount_codes.json",
                       shop_host,
                       payload={"discount_code": {"code": args.code}})
    code = (code_result.get("discount_code") or {}
            if isinstance(code_result, dict) else {})
    print(json.dumps({"ok": True, "price_rule_id": rule_id,
                      "title": rule.get("title"),
                      "value_type": rule.get("value_type"),
                      "value": rule.get("value"),
                      "code": code.get("code")}, indent=2))


def add_shop_arg(p):
    p.add_argument("--shop", required=True,
                   help="store, e.g. 'mystore' or 'mystore.myshopify.com'")
    return p


def main():
    parser = argparse.ArgumentParser(description="Shopify Admin API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = add_shop_arg(sub.add_parser("auth", help="verify the connection"))
    p.set_defaults(func=cmd_auth)

    p = add_shop_arg(sub.add_parser("orders", help="open orders"))
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_orders)

    p = add_shop_arg(sub.add_parser("products", help="products"))
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_products)

    p = add_shop_arg(sub.add_parser("customers", help="customers"))
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_customers)

    p = add_shop_arg(sub.add_parser(
        "product-create",
        help="create a draft product with one variant (needs --confirm)"))
    p.add_argument("--title", required=True)
    p.add_argument("--body-html", default="",
                   help="HTML product description")
    p.add_argument("--price", required=True,
                   help="variant price, e.g. 29.99")
    p.add_argument("--sku", default=None)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_product_create)

    p = add_shop_arg(sub.add_parser(
        "discount-create",
        help="create a discount (price rule + code) (needs --confirm)"))
    p.add_argument("--title", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--percent", type=float,
                       help="percentage off, e.g. 20 for 20%%")
    group.add_argument("--amount", type=float,
                       help="fixed amount off in store currency, e.g. 10")
    p.add_argument("--code", required=True,
                   help="the redeemable discount code")
    p.add_argument("--ends-at", default=None,
                   help="ISO end date, e.g. 2026-12-31T23:59:59Z")
    p.add_argument("--usage-limit", type=int, default=None)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_discount_create)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
