#!/usr/bin/env python3
"""Minimal NewsAPI CLI for the muse-connectors newsapi skill.

Auth: loads the per-user `custom.newsapi` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate into the `apiKey` query param on
approved egress, only to newsapi.org.

Note: NewsAPI returns {"status": "ok"|"error", ...}; the body is inspected and
error statuses exit with the API's code and message.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.newsapi"
ALLOWED_HOSTS = ("newsapi.org",)
API = "https://newsapi.org/v2"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        read_json_response,
        url_with_surrogate_query_param,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def call_get(path: str, params: dict) -> list:
    url = API + path + "?" + urllib.parse.urlencode(params)
    try:
        url = url_with_surrogate_query_param(
            url, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS
        )
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        sys.exit(f"error: HTTP {exc.code}: {body[:300]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if result.get("status") == "error":
        sys.exit(f"error: newsapi {result.get('code')}: {result.get('message')}")
    return result.get("articles", [])


def shape(articles: list) -> list:
    return [
        {"title": a.get("title"), "source": (a.get("source") or {}).get("name"),
         "url": a.get("url")}
        for a in articles
    ]


def cmd_headlines(args):
    articles = call_get(
        "/top-headlines", {"country": args.country, "pageSize": args.limit}
    )
    print(json.dumps(shape(articles), indent=2))


def cmd_search(args):
    articles = call_get(
        "/everything",
        {"q": args.query, "pageSize": args.limit, "sortBy": "publishedAt"},
    )
    print(json.dumps(shape(articles), indent=2))


def main():
    parser = argparse.ArgumentParser(description="NewsAPI CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("headlines", help="top headlines for a country")
    p.add_argument("--country", default="us")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_headlines)

    p = sub.add_parser("search", help="search all news")
    p.add_argument("--query", required=True)
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_search)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
