#!/usr/bin/env python3
"""Minimal Netlify API CLI for the muse-connectors netlify skill.

Auth: loads the per-user `custom.netlify` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api.netlify.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.netlify"
ALLOWED_HOSTS = ("api.netlify.com",)
API = "https://api.netlify.com/api/v1"

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
        sys.exit(f"error: netlify API returned HTTP {exc.code}: {body}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_sites(args):
    sites = call("/sites", params={"per_page": args.limit})
    out = [{"id": s.get("id"), "name": s.get("name"), "url": s.get("url"),
            "deploy_state": (s.get("published_deploy") or {}).get("state")}
           for s in sites]
    print(json.dumps(out, indent=2))


def cmd_deploys(args):
    site = urllib.parse.quote(args.site, safe="")
    deploys = call(f"/sites/{site}/deploys", params={"per_page": args.limit})
    out = [{"id": d.get("id"), "state": d.get("state"), "created_at": d.get("created_at")}
           for d in deploys]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Netlify API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("sites", help="list sites")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_sites)

    p = sub.add_parser("deploys", help="recent deploys for a site")
    p.add_argument("--site", required=True, help="site ID (from Site settings → API ID)")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_deploys)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
