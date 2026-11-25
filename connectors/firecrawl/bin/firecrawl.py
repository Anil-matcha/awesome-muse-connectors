#!/usr/bin/env python3
"""Minimal Firecrawl API CLI for the muse-connectors firecrawl skill.

Auth: loads the per-user `custom.firecrawl` credential as a surrogate via
the bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.firecrawl.dev.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.firecrawl"
ALLOWED_HOSTS = ("api.firecrawl.dev",)
API = "https://api.firecrawl.dev"

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


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", body.get("message", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: firecrawl returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    # Cheapest documented call: mapping a trivial URL still costs one credit.
    call("POST", "/v2/map", payload={"url": "https://example.com"})
    print(json.dumps({"ok": True}, indent=2))


def cmd_scrape(args):
    payload = {"url": args.url,
               "formats": args.formats.split(",") if args.formats else ["markdown"]}
    result = call("POST", "/v2/scrape", payload=payload)
    print(json.dumps(result, indent=2))


def cmd_crawl(args):
    payload = {"url": args.url}
    if args.limit:
        payload["limit"] = args.limit
    result = call("POST", "/v2/crawl", payload=payload)
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "url": result.get("url")}, indent=2))


def cmd_crawl_status(args):
    result = call("GET", f"/v2/crawl/{args.id}")
    print(json.dumps(result, indent=2))


def cmd_map(args):
    payload = {"url": args.url}
    if args.limit:
        payload["limit"] = args.limit
    result = call("POST", "/v2/map", payload=payload)
    print(json.dumps(result, indent=2))


def cmd_search(args):
    payload = {"query": args.query}
    if args.limit:
        payload["limit"] = args.limit
    result = call("POST", "/v2/search", payload=payload)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Firecrawl API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key (costs one map call)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("scrape", help="scrape one page (confirm first)")
    p.add_argument("--url", required=True)
    p.add_argument("--formats", default=None,
                   help="comma-separated: markdown,html,rawHtml,links,screenshot")
    p.set_defaults(func=cmd_scrape)

    p = sub.add_parser("crawl", help="start an async crawl (confirm first)")
    p.add_argument("--url", required=True)
    p.add_argument("--limit", type=int, default=None,
                   help="max pages to crawl")
    p.set_defaults(func=cmd_crawl)

    p = sub.add_parser("crawl-status", help="poll a crawl job")
    p.add_argument("--id", required=True, help="crawl job ID")
    p.set_defaults(func=cmd_crawl_status)

    p = sub.add_parser("map", help="list URLs on a site (confirm first)")
    p.add_argument("--url", required=True)
    p.add_argument("--limit", type=int, default=None,
                   help="max URLs to return")
    p.set_defaults(func=cmd_map)

    p = sub.add_parser("search", help="web search (confirm first)")
    p.add_argument("--query", required=True)
    p.add_argument("--limit", type=int, default=None,
                   help="max results")
    p.set_defaults(func=cmd_search)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
