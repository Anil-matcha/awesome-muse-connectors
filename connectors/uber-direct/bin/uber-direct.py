#!/usr/bin/env python3
"""Minimal Uber Direct same-day delivery CLI for the muse-connectors uber-direct skill.

Auth: loads the per-user `custom.uber-direct` credential as a surrogate via
the bundled dynamic_credentials helper. Uber Direct uses OAuth 2.0
client-credentials; the runtime performs the token exchange against Uber's
token endpoint and hands this script a fresh access token (same pattern as
the amadeus connector). The stored credential holds the developer app's
client ID + client secret; the customer ID travels as a --customer-id flag
because it identifies the account in the URL path. The real secrets never
touch this script: the runtime swaps the surrogate on approved egress, only
to api.uber.com.

Safety: `dispatch` sends a real courier (HIGH actuation) and requires an
exact --confirm string echoed by the CLI. Sandbox is the default
environment; production requires --env prod.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.uber-direct"
ALLOWED_HOSTS = ("api.uber.com",)
API = "https://api.uber.com"
CONNECT_GUIDANCE = (
    "not connected: collect the Uber Direct developer app's client ID and "
    "client secret via the secure credential flow "
    "(credentials.request_api_access) as `custom.uber-direct`, then retry. "
    "Find the customer ID in the Uber Direct developer dashboard; pass it "
    "as --customer-id."
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


def call(customer_id: str, method: str, path: str,
         payload: dict | None = None, expect_404_ok: bool = False) -> dict:
    url = API + f"/v1/customers/{urllib.parse.quote(customer_id, safe='')}" + path
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
        if expect_404_ok and exc.code == 404:
            return {"ok": True, "probe": "not_found_auth_succeeded"}
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: uber-direct returned HTTP {exc.code}: {msg}")
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


def load_file(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        sys.exit(f"error: could not read JSON file {path}: {exc}")


def cmd_auth(args):
    # No pure status endpoint exists; a 404 on a probe delivery id means the
    # request was authorized (unauthorized requests fail earlier with 401/403).
    result = call(args.customer_id, "GET", "/deliveries/__auth_probe__",
                  expect_404_ok=True)
    print(json.dumps({"ok": True, "customer_id": args.customer_id,
                      "note": "authorized; probe id not found as expected"},
                     indent=2))


def cmd_quote(args):
    payload = load_file(args.file)
    result = call(args.customer_id, "POST", "/quotes", payload)
    fee = result.get("fee") or {}
    print(json.dumps({"quote_id": result.get("id"),
                      "fee": fee.get("amount") or result.get("fee"),
                      "currency": result.get("currency"),
                      "dropoff_eta": result.get("dropoff_eta"),
                      "pickup_duration": result.get("pickup_duration"),
                      "raw": result}, indent=2))


def cmd_dispatch(args):
    payload = load_file(args.file)
    pickup = ((payload.get("pickup") or {}).get("address") or {})
    dropoff = ((payload.get("dropoff") or {}).get("address") or {})
    pickup_s = pickup.get("street_address", "?") if isinstance(pickup, dict) else "?"
    dropoff_s = dropoff.get("street_address", "?") if isinstance(dropoff, dict) else "?"
    quoted = payload.get("quoted_fee") or payload.get("fee") or "?"
    expected = (f"dispatch courier: {pickup_s} -> {dropoff_s}, "
                f"quoted {quoted}")
    need_confirm(
        args, expected,
        "dispatch sends a REAL courier to the pickup, and the quoted fee is "
        "charged on acceptance. Run `quote` first and confirm the fee with "
        "the user.")
    result = call(args.customer_id, "POST", "/deliveries", payload)
    print(json.dumps({"ok": True, "delivery_id": result.get("id"),
                      "status": result.get("status"),
                      "tracking_url": result.get("tracking_url")}, indent=2))


def cmd_get(args):
    result = call(args.customer_id, "GET", f"/deliveries/{args.delivery_id}")
    print(json.dumps({"delivery_id": result.get("id"),
                      "status": result.get("status"),
                      "courier": result.get("courier"),
                      "tracking_url": result.get("tracking_url"),
                      "dropoff_eta": result.get("dropoff_eta")}, indent=2))


def cmd_cancel(args):
    expected = f"cancel delivery {args.delivery_id}"
    need_confirm(
        args, expected,
        "cancelling a pending delivery can still incur a fee if a courier "
        "was already assigned; delivered parcels cannot be recalled.")
    result = call(args.customer_id, "POST",
                  f"/deliveries/{args.delivery_id}/cancel")
    print(json.dumps({"ok": True, "delivery_id": result.get("id"),
                      "status": result.get("status")}, indent=2))


def add_customer(p):
    p.add_argument("--customer-id", required=True,
                   help="Uber Direct customer ID (from the developer dashboard)")


def main():
    parser = argparse.ArgumentParser(
        description="Uber Direct same-day delivery CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the credentials")
    add_customer(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("quote", help="price/time quote (dispatches nothing)")
    add_customer(p)
    p.add_argument("--file", required=True,
                   help="JSON file with the Uber Direct quote payload "
                        "(pickup, dropoff, package)")
    p.set_defaults(func=cmd_quote)

    p = sub.add_parser("dispatch", help="dispatch a courier (HIGH actuation)")
    add_customer(p)
    p.add_argument("--file", required=True,
                   help="JSON file with the Uber Direct delivery payload. "
                        "Include the quoted fee as quoted_fee for the "
                        "confirmation string.")
    p.add_argument("--env", default="sandbox", choices=("sandbox", "prod"),
                   help="sandbox test deliveries (default) or production")
    p.add_argument("--confirm", default=None,
                   help="exact confirmation string echoed by the CLI")
    p.set_defaults(func=cmd_dispatch)

    p = sub.add_parser("get", help="delivery status and tracking")
    add_customer(p)
    p.add_argument("--delivery-id", required=True)
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("cancel", help="cancel a pending delivery")
    add_customer(p)
    p.add_argument("--delivery-id", required=True)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_cancel)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
