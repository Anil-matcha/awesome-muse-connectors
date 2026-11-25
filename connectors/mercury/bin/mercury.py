#!/usr/bin/env python3
"""Minimal Mercury API CLI for the muse-connectors Mercury skill.

Read-only: accounts and transactions. Auth: loads the per-user
`custom.mercury` credential as a surrogate via the bundled
dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api.mercury.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.mercury"
ALLOWED_HOSTS = ("api.mercury.com",)
API = "https://api.mercury.com/api/v1"

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
    result = call("/accounts")
    accounts = result.get("accounts", []) if isinstance(result, dict) else []
    print(json.dumps({"ok": True, "accounts": len(accounts)}, indent=2))


def cmd_accounts(_args):
    result = call("/accounts")
    out = [
        {"id": a.get("id"), "name": a.get("name"), "kind": a.get("kind"),
         "lastFourDigits": a.get("lastFourDigits")}
        for a in (result.get("accounts", []) if isinstance(result, dict) else [])
    ]
    print(json.dumps(out, indent=2))


def cmd_transactions(args):
    account = urllib.parse.quote(args.account, safe="")
    result = call(f"/account/{account}/transactions", params={"limit": args.limit})
    out = [
        {"id": t.get("id"), "amount": t.get("amount"), "status": t.get("status"),
         "counterpartyName": t.get("counterpartyName"), "createdAt": t.get("createdAt")}
        for t in (result.get("transactions", []) if isinstance(result, dict) else [])
    ]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Mercury API CLI (muse-connectors, read-only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("accounts", help="list bank accounts")
    p.set_defaults(func=cmd_accounts)

    p = sub.add_parser("transactions", help="recent transactions for an account")
    p.add_argument("--account", required=True, help="account ID")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_transactions)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
