#!/usr/bin/env python3
"""Minimal DigitalOcean API CLI for the muse-connectors digitalocean skill.

Auth: loads the per-user `custom.digitalocean` credential as a surrogate via
the bundled dynamic_credentials helper. The real token never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.digitalocean.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.digitalocean"
ALLOWED_HOSTS = ("api.digitalocean.com",)
API = "https://api.digitalocean.com/v2"

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


def call(path: str, params: dict | None = None) -> dict:
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
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        sys.exit(f"error: digitalocean API returned HTTP {exc.code}: {body}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_droplets(args):
    result = call("/droplets", params={"per_page": args.limit})
    out = [{"id": d.get("id"), "name": d.get("name"), "status": d.get("status"),
            "region": (d.get("region") or {}).get("slug")}
           for d in result.get("droplets", [])]
    print(json.dumps(out, indent=2))


def cmd_domains(_args):
    result = call("/domains")
    out = [{"name": d.get("name"), "ttl": d.get("ttl")}
           for d in result.get("domains", [])]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="DigitalOcean API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("droplets", help="list droplets")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_droplets)

    p = sub.add_parser("domains", help="list domains")
    p.set_defaults(func=cmd_domains)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
