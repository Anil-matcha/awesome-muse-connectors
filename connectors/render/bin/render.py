#!/usr/bin/env python3
"""Minimal Render API CLI for the muse-connectors render skill.

Auth: loads the per-user `custom.render` credential as a surrogate via the
bundled dynamic_credentials helper. The real key never touches this script:
the runtime swaps the surrogate on approved egress, only to api.render.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.render"
ALLOWED_HOSTS = ("api.render.com",)
API = "https://api.render.com/v1"

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
        sys.exit(f"error: render API returned HTTP {exc.code}: {body}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_services(args):
    services = call("/services", params={"limit": args.limit})
    out = [{"id": s.get("id"), "name": s.get("name"), "type": s.get("type"),
            "region": (s.get("serviceDetails") or {}).get("region")}
           for s in services]
    print(json.dumps(out, indent=2))


def cmd_deploys(args):
    service = urllib.parse.quote(args.service, safe="")
    deploys = call(f"/services/{service}/deploys", params={"limit": args.limit})
    out = [{"id": d.get("id"), "status": d.get("status"), "createdAt": d.get("createdAt")}
           for d in deploys]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Render API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("services", help="list services")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_services)

    p = sub.add_parser("deploys", help="recent deploys for a service")
    p.add_argument("--service", required=True, help="service ID, e.g. srv-abc123")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_deploys)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
