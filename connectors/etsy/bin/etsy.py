#!/usr/bin/env python3
"""Minimal Etsy Open API CLI for the muse-connectors etsy skill.

Auth: OAuth 2.0 (`Authorization: Bearer <token>`) PLUS the app keystring in
the `x-api-key` header. The `custom.etsy` credential holds both: the
`access_token` entry is the OAuth token, the `keystring` entry is the API
keystring. Both are loaded as surrogates via the bundled
dynamic_credentials helper; the real values never touch this script. The
runtime swaps the surrogates on approved egress, only to openapi.etsy.com.

NOTE: the API key must be approved in the Etsy developer portal before any
call works. Listing writes carry fees; they are confirmation-gated.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.etsy"
ALLOWED_HOSTS = ("openapi.etsy.com",)
API = "https://openapi.etsy.com/v3/application"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        add_surrogate_to_request,
        dynamic_credential_entry,
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
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        # OAuth token via the credential's bearer placement.
        add_surrogate_to_request(req, CREDENTIAL_NAME,
                                 allowed_hosts=ALLOWED_HOSTS)
        # API keystring in the x-api-key header.
        keystring = dynamic_credential_entry(CREDENTIAL_NAME,
                                             "keystring")["surrogate"]
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    req.add_header("x-api-key", keystring)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: etsy returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def list_of(result: dict, key: str = "results") -> list:
    if not isinstance(result, dict):
        return []
    items = result.get(key, [])
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
    result = call("GET", f"/shops/{args.shop_id}/receipts",
                  params={"limit": 1})
    print(json.dumps({"ok": True, "shop_id": args.shop_id,
                      "receipts": len(list_of(result))}, indent=2))


def cmd_receipts(args):
    params = {"limit": args.limit, "offset": args.offset}
    result = call("GET", f"/shops/{args.shop_id}/receipts", params=params)
    receipts = [
        {"receipt_id": r.get("receipt_id"),
         "create_timestamp": r.get("create_timestamp"),
         "grandtotal": r.get("grandtotal"), "total_tax_cost": r.get("total_tax_cost"),
         "name": r.get("name"), "state": r.get("state")}
        for r in list_of(result)
    ]
    print(json.dumps(receipts, indent=2))


def cmd_listings(args):
    params = {"limit": args.limit, "offset": args.offset,
              "state": "active", "includes": "Images,Shop"}
    result = call("GET", f"/shops/{args.shop_id}/listings/active",
                  params=params)
    listings = [
        {"listing_id": l.get("listing_id"), "title": l.get("title"),
         "price": l.get("price"), "quantity": l.get("quantity"),
         "views": l.get("views"), "url": l.get("url")}
        for l in list_of(result)
    ]
    print(json.dumps(listings, indent=2))


def cmd_listing_create(args):
    result = call("POST", f"/shops/{args.shop_id}/listings",
                  payload=load_json(args.json))
    print(json.dumps({"ok": True, "listing_id": result.get("listing_id"),
                      "state": result.get("state")}, indent=2))


def cmd_transactions(args):
    params = {"limit": args.limit, "offset": args.offset}
    result = call("GET", f"/shops/{args.shop_id}/transactions", params=params)
    txns = [
        {"transaction_id": t.get("transaction_id"),
         "listing_id": t.get("listing_id"), "title": t.get("title"),
         "price": t.get("price"), "quantity": t.get("quantity"),
         "create_timestamp": t.get("create_timestamp")}
        for t in list_of(result)
    ]
    print(json.dumps(txns, indent=2))


def cmd_ledger(args):
    params = {"limit": args.limit, "offset": args.offset}
    result = call("GET",
                  f"/shops/{args.shop_id}/payment-account/ledger-entries",
                  params=params)
    entries = [
        {"entry_id": e.get("entry_id"), "entry_type": e.get("entry_type"),
         "amount": e.get("amount"), "currency": e.get("currency"),
         "create_date": e.get("create_date"),
         "description": e.get("description")}
        for e in list_of(result, key="ledger_entries")
    ]
    print(json.dumps(entries, indent=2))


def add_shop(p):
    p.add_argument("--shop-id", required=True, help="Etsy shop ID")


def main():
    parser = argparse.ArgumentParser(description="Etsy Open API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify OAuth token and keystring")
    add_shop(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("receipts", help="list shop receipts (orders)")
    add_shop(p)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--offset", type=int, default=0)
    p.set_defaults(func=cmd_receipts)

    p = sub.add_parser("listings", help="list active listings")
    add_shop(p)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--offset", type=int, default=0)
    p.set_defaults(func=cmd_listings)

    p = sub.add_parser("listing-create",
                       help="create a listing (confirm first; incurs the $0.20 listing fee)")
    add_shop(p)
    p.add_argument("--json", required=True,
                   help="listing payload as a JSON object string")
    p.set_defaults(func=cmd_listing_create)

    p = sub.add_parser("transactions", help="list shop transactions")
    add_shop(p)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--offset", type=int, default=0)
    p.set_defaults(func=cmd_transactions)

    p = sub.add_parser("ledger", help="list payment-account ledger entries")
    add_shop(p)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--offset", type=int, default=0)
    p.set_defaults(func=cmd_ledger)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
