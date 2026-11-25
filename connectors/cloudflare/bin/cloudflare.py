#!/usr/bin/env python3
"""Minimal Cloudflare API CLI for the muse-connectors cloudflare skill.

Auth: loads the per-user `custom.cloudflare` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api.cloudflare.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.cloudflare"
ALLOWED_HOSTS = ("api.cloudflare.com",)
API = "https://api.cloudflare.com/client/v4"

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


def call(path: str, params: dict | None = None) -> list:
    """Call the API and unwrap Cloudflare's {"success", "result"} envelope."""
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        sys.exit(f"error: cloudflare API returned HTTP {exc.code}: {body}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if not result.get("success"):
        sys.exit(f"error: cloudflare: {json.dumps(result.get('errors'))}")
    return result.get("result", [])


def cmd_zones(args):
    zones = call("/zones", params={"per_page": args.limit})
    out = [{"id": z.get("id"), "name": z.get("name"), "status": z.get("status")}
           for z in zones]
    print(json.dumps(out, indent=2))


def cmd_dns(args):
    zone = urllib.parse.quote(args.zone, safe="")
    records = call(f"/zones/{zone}/dns_records", params={"per_page": args.limit})
    out = [{"id": r.get("id"), "type": r.get("type"), "name": r.get("name"),
            "content": r.get("content"), "proxied": r.get("proxied")}
           for r in records]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Cloudflare API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("zones", help="list zones")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_zones)

    p = sub.add_parser("dns", help="DNS records for a zone")
    p.add_argument("--zone", required=True, help="zone ID (from `zones`)")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_dns)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
