#!/usr/bin/env python3
"""Minimal Square POS + Terminal API CLI for the muse-connectors square skill.

Auth: loads the per-user `custom.square` credential as a surrogate via the
bundled dynamic_credentials helper. Square uses OAuth 2.0 bearer tokens (or
a personal access token for single-account use); the runtime performs the
token exchange/refresh and hands this script a fresh access token (same
pattern as the amadeus connector). The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to
connect.squareup.com or connect.squareupsandbox.com.

Safety: SANDBOX IS THE DEFAULT and never moves real money. Terminal
checkouts and direct charges are HIGH actuations and require an exact
--confirm string echoed by the CLI. Refunds are MEDIUM and require
--confirm on every call.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.square"
ALLOWED_HOSTS = ("connect.squareup.com", "connect.squareupsandbox.com")
BASES = {
    "sandbox": "https://connect.squareupsandbox.com",
    "prod": "https://connect.squareup.com",
}
CONNECT_GUIDANCE = (
    "not connected: collect a Square OAuth app token or a personal access "
    "token (Square Developer Dashboard) via the secure credential flow "
    "(credentials.request_api_access) as `custom.square`, then retry."
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


def call(env: str, method: str, path: str, payload: dict | None = None) -> dict:
    url = BASES[env] + path
    data = None
    headers = {"Square-Version": "2026-08-20"}
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
            errs = body.get("errors", [])
            msg = errs[0].get("detail", str(exc)) if errs else str(exc)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: square returned HTTP {exc.code}: {msg}")
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


def fmt_amount(cents: int, currency: str) -> str:
    return f"${cents / 100:,.2f} {currency}"


def load_file(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        sys.exit(f"error: could not read JSON file {path}: {exc}")


def add_env(p):
    p.add_argument("--env", default="sandbox", choices=("sandbox", "prod"),
                   help="sandbox (default, never moves real money) or prod")


def cmd_auth(args):
    result = call(args.env, "GET", "/v2/locations")
    locs = [{"id": l.get("id"), "name": l.get("name")}
            for l in result.get("locations", [])]
    print(json.dumps({"ok": True, "env": args.env, "locations": locs},
                     indent=2))


def cmd_locations(args):
    result = call(args.env, "GET", "/v2/locations")
    locs = [{"id": l.get("id"), "name": l.get("name"),
             "status": l.get("status"),
             "capabilities": l.get("capabilities")}
            for l in result.get("locations", [])]
    print(json.dumps(locs, indent=2))


def cmd_payments(args):
    result = call(args.env, "GET", f"/v2/payments?limit={args.limit}")
    pays = [{"id": p.get("id"),
             "amount_money": p.get("amount_money"),
             "status": p.get("status"),
             "created_at": p.get("created_at")}
            for p in result.get("payments", [])]
    print(json.dumps(pays, indent=2))


def cmd_payment_get(args):
    result = call(args.env, "GET", f"/v2/payments/{args.payment_id}")
    p = result.get("payment", {})
    print(json.dumps({"id": p.get("id"), "amount_money": p.get("amount_money"),
                      "status": p.get("status"),
                      "source_type": p.get("source_type"),
                      "created_at": p.get("created_at")}, indent=2))


def cmd_order_create(args):
    payload = load_file(args.file)
    result = call(args.env, "POST", "/v2/orders",
                  {"idempotency_key": str(uuid.uuid4()), "order": payload})
    order = result.get("order", {})
    print(json.dumps({"ok": True, "order_id": order.get("id"),
                      "state": order.get("state"),
                      "note": "order record only; no money moved"}, indent=2))


def cmd_checkout_create(args):
    amount = fmt_amount(args.amount_cents, args.currency)
    expected = (f"present {amount} charge on terminal {args.device_id}")
    need_confirm(
        args, expected,
        "a terminal checkout presents a charge on a PHYSICAL terminal; a "
        "customer tap captures real funds (in production).")
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "checkout": {
            "amount_money": {"amount": args.amount_cents,
                             "currency": args.currency},
            "device_options": {"device_id": args.device_id},
        },
    }
    if args.order_id:
        payload["checkout"]["order_id"] = args.order_id
    result = call(args.env, "POST", "/v2/terminals/checkouts", payload)
    co = result.get("checkout", {})
    print(json.dumps({"ok": True, "checkout_id": co.get("id"),
                      "status": co.get("status"),
                      "env": args.env}, indent=2))


def cmd_checkout_get(args):
    result = call(args.env, "GET",
                  f"/v2/terminals/checkouts/{args.checkout_id}")
    co = result.get("checkout", {})
    print(json.dumps({"checkout_id": co.get("id"), "status": co.get("status"),
                      "amount_money": co.get("amount_money"),
                      "payment_ids": co.get("payment_ids")}, indent=2))


def cmd_checkout_cancel(args):
    expected = f"cancel terminal checkout {args.checkout_id}"
    need_confirm(args, expected, "cancelling a pending terminal checkout.")
    result = call(args.env, "POST",
                  f"/v2/terminals/checkouts/{args.checkout_id}/cancel")
    co = result.get("checkout", {})
    print(json.dumps({"ok": True, "checkout_id": co.get("id"),
                      "status": co.get("status")}, indent=2))


def cmd_charge(args):
    amount = fmt_amount(args.amount_cents, args.currency)
    expected = f"charge {amount} to payment source {args.source_id}"
    need_confirm(
        args, expected,
        "a direct charge moves REAL funds from the payment source "
        "immediately (in production).")
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "source_id": args.source_id,
        "amount_money": {"amount": args.amount_cents,
                        "currency": args.currency},
    }
    if args.location_id:
        payload["location_id"] = args.location_id
    result = call(args.env, "POST", "/v2/payments", payload)
    p = result.get("payment", {})
    print(json.dumps({"ok": True, "payment_id": p.get("id"),
                      "status": p.get("status"),
                      "amount_money": p.get("amount_money"),
                      "env": args.env}, indent=2))


def cmd_refund(args):
    amount = fmt_amount(args.amount_cents, args.currency)
    expected = f"refund {amount} on payment {args.payment_id}"
    need_confirm(
        args, expected,
        "a refund sends money BACK to the customer; it is hard to take "
        "back once processed.")
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "payment_id": args.payment_id,
        "amount_money": {"amount": args.amount_cents,
                        "currency": args.currency},
    }
    result = call(args.env, "POST", "/v2/refunds", payload)
    r = result.get("refund", {})
    print(json.dumps({"ok": True, "refund_id": r.get("id"),
                      "status": r.get("status"),
                      "amount_money": r.get("amount_money"),
                      "env": args.env}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Square POS + Terminal API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the token")
    add_env(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("locations", help="list seller locations")
    add_env(p)
    p.set_defaults(func=cmd_locations)

    p = sub.add_parser("payments", help="list payments")
    add_env(p)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_payments)

    p = sub.add_parser("payment-get", help="retrieve one payment")
    add_env(p)
    p.add_argument("--payment-id", required=True)
    p.set_defaults(func=cmd_payment_get)

    p = sub.add_parser("order-create",
                       help="create an order record (moves no money)")
    add_env(p)
    p.add_argument("--file", required=True,
                   help="JSON file with the Square order object")
    p.set_defaults(func=cmd_order_create)

    p = sub.add_parser("checkout-create",
                       help="push a charge to a physical Terminal (HIGH)")
    add_env(p)
    p.add_argument("--device-id", required=True)
    p.add_argument("--amount-cents", type=int, required=True)
    p.add_argument("--currency", default="USD")
    p.add_argument("--order-id", default=None)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_checkout_create)

    p = sub.add_parser("checkout-get", help="Terminal checkout status")
    add_env(p)
    p.add_argument("--checkout-id", required=True)
    p.set_defaults(func=cmd_checkout_get)

    p = sub.add_parser("checkout-cancel", help="cancel a pending checkout")
    add_env(p)
    p.add_argument("--checkout-id", required=True)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_checkout_cancel)

    p = sub.add_parser("charge", help="charge a payment source (HIGH)")
    add_env(p)
    p.add_argument("--source-id", required=True,
                   help="card on file id or card nonce")
    p.add_argument("--amount-cents", type=int, required=True)
    p.add_argument("--currency", default="USD")
    p.add_argument("--location-id", default=None)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_charge)

    p = sub.add_parser("refund", help="refund a payment (MEDIUM)")
    add_env(p)
    p.add_argument("--payment-id", required=True)
    p.add_argument("--amount-cents", type=int, required=True)
    p.add_argument("--currency", default="USD")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_refund)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
