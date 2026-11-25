#!/usr/bin/env python3
"""Minimal Shippo multi-carrier shipping CLI for the muse-connectors shippo skill.

Auth: loads the per-user `custom.shippo` API token as a surrogate via the
bundled dynamic_credentials helper. Shippo authenticates with the raw token
in the `Authorization` header (no Bearer prefix); the placement is resolved
by the helper from the credential config. The real token never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.goshippo.com.

Safety: buying a label (`buy`) is a HIGH actuation (real postage, real money,
physical parcel transport). It requires --confirm with the exact string the
CLI echoes, and --live is required when running against a production key.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.shippo"
ALLOWED_HOSTS = ("api.goshippo.com",)
API = "https://api.goshippo.com"
CONNECT_GUIDANCE = (
    "not connected: collect a Shippo API token (Shippo dashboard -> API) via "
    "the secure credential flow (credentials.request_api_access) as "
    "`custom.shippo`, then retry. Use a test key for dry runs."
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


def call(method: str, path: str, payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
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
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("detail", body.get("message", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: shippo returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def load_file(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        sys.exit(f"error: could not read JSON file {path}: {exc}")


def cmd_auth(_args):
    result = call("GET", "/shipments?results=1")
    print(json.dumps({"ok": True,
                      "shipments_total": result.get("count")}, indent=2))


def cmd_rates(args):
    payload = load_file(args.file)
    result = call("POST", "/shipments", payload)
    rates = [
        {"object_id": r.get("object_id"),
         "provider": r.get("provider"),
         "servicelevel": (r.get("servicelevel") or {}).get("name"),
         "amount": r.get("amount"), "currency": r.get("currency"),
         "estimated_days": r.get("estimated_days"),
         "duration_terms": r.get("duration_terms"),
         "test": r.get("test")}
        for r in result.get("rates", [])
    ]
    print(json.dumps({"shipment_id": result.get("object_id"),
                      "rates": rates}, indent=2))


def cmd_get_shipment(args):
    result = call("GET", f"/shipments/{args.id}")
    print(json.dumps({"object_id": result.get("object_id"),
                      "status": result.get("status"),
                      "rates": [{"object_id": r.get("object_id"),
                                 "provider": r.get("provider"),
                                 "amount": r.get("amount"),
                                 "currency": r.get("currency")}
                                for r in result.get("rates", [])]},
                     indent=2))


def cmd_track(args):
    carrier = urllib.parse.quote(args.carrier, safe="")
    number = urllib.parse.quote(args.number, safe="")
    result = call("GET", f"/tracks/{carrier}/{number}")
    history = [{"status": e.get("status"),
                "status_date": e.get("status_date"),
                "location": (e.get("location") or {}).get("city")}
               for e in result.get("tracking_history", [])]
    print(json.dumps({"carrier": result.get("carrier"),
                      "tracking_number": result.get("tracking_number"),
                      "tracking_status": (result.get("tracking_status") or {})
                      .get("status"),
                      "history": history}, indent=2))


def cmd_buy(args):
    # Verify the confirmation BEFORE any money moves. Resolve the rate from
    # the documented shipment resource so the expected string is exact.
    shipment = call("GET", f"/shipments/{args.shipment_id}")
    rate = next((r for r in shipment.get("rates", [])
                 if r.get("object_id") == args.rate_id), None)
    if not rate:
        sys.exit(f"error: rate {args.rate_id} not found on shipment "
                 f"{args.shipment_id}")
    service = (rate.get("servicelevel") or {}).get("name") or ""
    expected = (f"buy {rate.get('amount')} {rate.get('currency')} "
                f"{rate.get('provider')} {service} label "
                f"for rate {args.rate_id}".strip())
    if args.live and not args.confirm:
        sys.exit(
            "refusing: --live was given without confirmation.\n"
            "A production purchase buys real postage and bills the account "
            "immediately. Re-run with --live and the exact confirmation "
            "string, e.g.\n"
            f'  --confirm "{expected}"'
        )
    if args.confirm != expected:
        sys.exit(
            "confirmation required before buying this label. "
            "Re-run with the exact string:\n"
            f'  --confirm "{expected}"'
        )
    result = call("POST", "/transactions", {"rate": args.rate_id})
    print(json.dumps({"ok": True, "transaction_id": result.get("object_id"),
                      "status": result.get("status"),
                      "tracking_number": result.get("tracking_number"),
                      "label_url": result.get("label_url"),
                      "test": result.get("test", True)}, indent=2))


def cmd_refund(args):
    result = call("POST", "/refunds", {"transaction": args.transaction_id})
    print(json.dumps({"ok": True, "refund_id": result.get("object_id"),
                      "status": result.get("status")}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Shippo multi-carrier shipping CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("rates", help="rates for a shipment (buys nothing)")
    p.add_argument("--file", required=True,
                   help="JSON file with the Shippo shipment object "
                        "(address_from, address_to, parcels)")
    p.set_defaults(func=cmd_rates)

    p = sub.add_parser("get-shipment", help="retrieve a shipment")
    p.add_argument("--id", required=True, help="shipment object id")
    p.set_defaults(func=cmd_get_shipment)

    p = sub.add_parser("track", help="tracking status for a parcel")
    p.add_argument("--carrier", required=True, help="e.g. usps, ups, fedex")
    p.add_argument("--number", required=True, help="tracking number")
    p.set_defaults(func=cmd_track)

    p = sub.add_parser("buy", help="buy a label from a rate (HIGH actuation)")
    p.add_argument("--shipment-id", required=True,
                   help="shipment object id from the rates command")
    p.add_argument("--rate-id", required=True,
                   help="rate object id from the rates command")
    p.add_argument("--live", action="store_true",
                   help="acknowledge this runs against a production key")
    p.add_argument("--confirm", default=None,
                   help="exact confirmation string echoed by the CLI")
    p.set_defaults(func=cmd_buy)

    p = sub.add_parser("refund", help="refund/void an unused label")
    p.add_argument("--transaction-id", required=True,
                   help="transaction object id from the buy command")
    p.set_defaults(func=cmd_refund)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
