#!/usr/bin/env python3
"""Minimal Brave Search CLI for the muse-connectors brave-search skill.

Auth: loads the per-user `custom.brave-search` credential as a surrogate via
the bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.search.brave.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.brave-search"
ALLOWED_HOSTS = ("api.search.brave.com",)
API = "https://api.search.brave.com/res/v1"

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


def call_get(path: str, params: dict) -> dict:
    url = API + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        sys.exit(f"error: HTTP {exc.code}: {body[:300]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    call_get("/web/search", {"q": "test", "count": 1})
    print(json.dumps({"ok": True}, indent=2))


def cmd_search(args):
    count = max(1, min(20, args.count))
    result = call_get("/web/search", {"q": args.query, "count": count})
    out = [
        {"title": r.get("title"), "url": r.get("url"), "description": r.get("description")}
        for r in (result.get("web") or {}).get("results", [])
    ]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Brave Search CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("search", help="web search via Brave's index")
    p.add_argument("--query", required=True)
    p.add_argument("--count", type=int, default=10, help="1-20, clamped")
    p.set_defaults(func=cmd_search)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
