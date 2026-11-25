#!/usr/bin/env python3
"""Minimal Keenable search and fetch CLI for the muse-connectors keenable skill.

Auth: an API key is optional. On a Muse runtime the per-user `custom.keenable`
credential is loaded as a surrogate via the bundled dynamic_credentials helper,
so the real key never touches this script; outside Muse the key is read from
the KEENABLE_API_KEY environment variable. With a key, requests go to the keyed
endpoints (/v1/search, /v1/fetch). With neither, they go to the keyless twins
(/v1/search/public, /v1/fetch/public), which are rate limited per IP.
Every request names this connector in the X-Keenable-Title header, which the
keyless endpoints require. The only host contacted is api.keenable.ai.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.keenable"
ENV_KEY = "KEENABLE_API_KEY"
ALLOWED_HOSTS = ("api.keenable.ai",)
API = "https://api.keenable.ai"
APP_TITLE = "awesome-muse-connectors"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import DynamicCredentialError, add_surrogate_to_request
except ImportError:  # not on a Muse runtime: env var or keyless only
    DynamicCredentialError = Exception
    add_surrogate_to_request = None


def attach_key(req: urllib.request.Request) -> str:
    """Attach the key to the X-API-Key header if one is set. Returns the auth mode."""
    key = os.environ.get(ENV_KEY, "").strip()
    if any(ch.isspace() or not ch.isprintable() for ch in key):
        # Never echo the key itself in the error.
        sys.exit(f"error: {ENV_KEY} contains whitespace or control characters")
    if key:
        req.add_header("X-API-Key", key)
        return "env"
    if add_surrogate_to_request is not None:
        try:
            add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
            return "muse"
        except DynamicCredentialError:
            pass
    return "none"


def call(path: str, params: dict | None = None, payload: dict | None = None):
    """Call the keyed endpoint when a key is set, else its keyless /public twin."""
    query = "?" + urllib.parse.urlencode(params) if params else ""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", "X-Keenable-Title": APP_TITLE}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path + query, data=data, headers=headers)
    mode = attach_key(req)
    if mode == "none":
        req = urllib.request.Request(API + path + "/public" + query, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        sys.exit(f"error: keenable returned HTTP {exc.code}: {body[:300]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    return result, mode


def cmd_auth(_args):
    result, mode = call("/v1/search", payload={"query": "test", "max_results": 1})
    labels = {
        "env": f"X-API-Key from {ENV_KEY}",
        "muse": f"X-API-Key from {CREDENTIAL_NAME}",
        "none": "no key (keyless, rate limited per IP)",
    }
    print(json.dumps({"ok": True, "auth": labels[mode],
                      "results": len(result.get("results", []))}, indent=2))


def cmd_search(args):
    payload = {"query": args.query, "max_results": max(1, min(50, args.limit))}
    if args.site:
        payload["site"] = args.site
    if args.published_after:
        payload["published_after"] = args.published_after
    if args.published_before:
        payload["published_before"] = args.published_before
    result, _mode = call("/v1/search", payload=payload)
    out = []
    for r in result.get("results", []):
        item = {
            "title": r.get("title"),
            "url": r.get("url"),
            "snippet": (r.get("snippet") or r.get("description") or "")[:500],
        }
        if r.get("published_at"):
            item["published_at"] = r["published_at"]
        out.append(item)
    print(json.dumps(out, indent=2))


def cmd_fetch(args):
    parts = urllib.parse.urlsplit(args.url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        sys.exit(f"error: --url must be an http(s) URL: {args.url}")
    max_chars = max(1, args.max_chars)
    params = {"url": args.url, "max_chars": max_chars}
    result, _mode = call("/v1/fetch", params=params)
    out = {k: result.get(k) for k in ("url", "title", "author", "published_at") if result.get(k)}
    # The API cuts at a word boundary, so it can run slightly over; cap locally.
    out["content"] = (result.get("content") or "")[:max_chars]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Keenable search and fetch CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection and show the auth mode")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("search", help="web search with ranked sources and snippets")
    p.add_argument("--query", required=True)
    p.add_argument("--limit", type=int, default=5, help="1-50, clamped")
    p.add_argument("--site", default=None, help="restrict to one site, e.g. python.org")
    p.add_argument("--published-after", default=None, help="YYYY-MM-DD")
    p.add_argument("--published-before", default=None, help="YYYY-MM-DD")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("fetch", help="read one page as markdown")
    p.add_argument("--url", required=True)
    p.add_argument("--max-chars", type=int, default=10000,
                   help="max characters of page content (default 10000)")
    p.set_defaults(func=cmd_fetch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
