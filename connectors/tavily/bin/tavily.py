#!/usr/bin/env python3
"""Minimal Tavily API CLI for the muse-connectors Tavily skill.

Auth: loads the per-user `custom.tavily` credential (an API key) as a
surrogate via the bundled dynamic_credentials helper. The real key never
touches this script: the runtime swaps the surrogate on approved egress, only
to api.tavily.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.tavily"
ALLOWED_HOSTS = ("api.tavily.com",)
API = "https://api.tavily.com"

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


def cmd_search(args):
    payload = {
        "query": args.query,
        "max_results": args.max_results,
        "search_depth": "advanced",
        "include_answer": True,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API + "/search", data=data, headers={"Content-Type": "application/json"}
    )
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = read_json_response(resp)
    except Exception as exc:  # network-level failure (HTTP errors surface here)
        sys.exit(f"error: request failed: {exc}")
    results = [
        {"title": r.get("title"), "url": r.get("url"),
         "content": (r.get("content") or "")[:600]}
        for r in result.get("results", [])
    ]
    print(json.dumps({"answer": result.get("answer"), "results": results}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Tavily search CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search", help="web search with AI answer")
    p.add_argument("--query", required=True)
    p.add_argument("--max-results", type=int, default=5)
    p.set_defaults(func=cmd_search)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
