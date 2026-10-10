#!/usr/bin/env python3
"""Minimal Datacircle CLI for the muse-connectors datacircle skill.

Auth: loads the per-user `custom.datacircle` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this script:
the runtime swaps the surrogate on approved egress, only to api.datacircle.dev.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.datacircle"
ALLOWED_HOSTS = ("api.datacircle.dev",)
API = "https://api.datacircle.dev"

# Each provider's own request, sent to api.datacircle.dev, and its price per profile in dollars.
PROVIDERS = {
    "up2data": {"method": "POST", "path": "/v1/profiles/enrich", "param": "url", "price": 0.002375},
    "harvestapi": {"method": "GET", "path": "/linkedin/profile", "param": "url", "price": 0.0037},
    "fetchin": {"method": "GET", "path": "/api/v1/profile", "param": "profileUrlOrUrn", "price": 0.001485},
}

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


def call(method: str, path: str, payload: dict | None = None, headers: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})}
    )
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        hint = {
            402: " (the balance can't cover the call: add funds, from $5, on the dashboard)",
            429: " (the provider's daily limit: ask the user, then call again with another --provider)",
        }.get(exc.code, "")
        sys.exit(f"error: HTTP {exc.code}{hint}: {body[:300]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = call("GET", "/balance/")
    print(json.dumps({"ok": True, "balance_usd": result.get("balance_usd")}, indent=2))


def cmd_balance(_args):
    print(json.dumps(call("GET", "/balance/"), indent=2))


def cmd_profile(args):
    provider = PROVIDERS[args.provider]
    if not args.confirm:
        print(json.dumps({
            "ok": False,
            "looked_up": False,
            "provider": args.provider,
            "price_usd": provider["price"],
            "next": "tell the user the provider and the price, and run again with --confirm after their yes",
        }, indent=2))
        return
    headers = {"X-Data-Provider": args.provider}
    if provider["method"] == "POST":
        result = call("POST", provider["path"], {provider["param"]: args.url}, headers)
    else:
        query = urllib.parse.urlencode({provider["param"]: args.url})
        result = call("GET", f"{provider['path']}?{query}", None, headers)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Datacircle CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("balance", help="the balance in dollars, free")
    p.set_defaults(func=cmd_balance)

    p = sub.add_parser("profile", help="one LinkedIn profile by its URL, paid from the balance")
    p.add_argument("--url", required=True, help="the profile's LinkedIn URL")
    p.add_argument("--provider", choices=sorted(PROVIDERS), default="up2data")
    p.add_argument("--confirm", action="store_true", help="the user said yes to the price")
    p.set_defaults(func=cmd_profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
