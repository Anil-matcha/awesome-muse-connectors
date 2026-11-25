#!/usr/bin/env python3
"""Minimal Wise API CLI for the muse-connectors Wise skill.

Read-only: profiles and multi-currency balances. Auth: loads the per-user
`custom.wise` credential as a surrogate via the bundled
dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api.wise.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.wise"
ALLOWED_HOSTS = ("api.wise.com",)
API = "https://api.wise.com"

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


def cmd_profiles(_args):
    result = call("/v1/profiles")
    if not isinstance(result, list):
        sys.exit(f"error: unexpected profiles response: {json.dumps(result)[:300]}")
    out = [{"id": p.get("id"), "type": p.get("type")} for p in result]
    print(json.dumps(out, indent=2))


def cmd_balances(args):
    profile = urllib.parse.quote(str(args.profile), safe="")
    result = call(f"/v4/profiles/{profile}/balances", params={"types": "STANDARD"})
    if not isinstance(result, list):
        sys.exit(f"error: unexpected balances response: {json.dumps(result)[:300]}")
    out = [
        {"currency": b.get("currency"), "balance": (b.get("amount") or {}).get("value")}
        for b in result
    ]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Wise API CLI (muse-connectors, read-only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("profiles", help="list profiles (also the status check)")
    p.set_defaults(func=cmd_profiles)

    p = sub.add_parser("balances", help="multi-currency balances for a profile")
    p.add_argument("--profile", required=True, help="profile ID")
    p.set_defaults(func=cmd_balances)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
