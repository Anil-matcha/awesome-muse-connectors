#!/usr/bin/env python3
"""Minimal Exa search CLI for the muse-connectors exa skill.

Auth: loads the per-user `custom.exa` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this script:
the runtime swaps the surrogate on approved egress, only to api.exa.ai.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.exa"
ALLOWED_HOSTS = ("api.exa.ai",)
API = "https://api.exa.ai"

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


def call_post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API + path, data=data, headers={"Content-Type": "application/json"}
    )
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
    result = call_post("/search", {"query": "test", "numResults": 1, "type": "auto"})
    print(json.dumps({"ok": True, "results": len(result.get("results", []))}, indent=2))


def cmd_search(args):
    result = call_post(
        "/search",
        {
            "query": args.query,
            "numResults": args.limit,
            "type": "auto",
            "contents": {"text": {"maxCharacters": 500}},
        },
    )
    out = [
        {
            "title": r.get("title"),
            "url": r.get("url"),
            "text": (r.get("text") or "")[:500],
        }
        for r in result.get("results", [])
    ]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Exa neural search CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("search", help="neural web search with page text")
    p.add_argument("--query", required=True)
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(func=cmd_search)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
