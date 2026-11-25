#!/usr/bin/env python3
"""Minimal Alpha Vantage CLI for the muse-connectors alphavantage skill.

Auth: loads the per-user `custom.alphavantage` credential as a surrogate via
the bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate into the `apikey` query param on
approved egress, only to www.alphavantage.co.

Note: Alpha Vantage returns HTTP 200 even for errors, so the JSON body is
inspected for "Error Message", "Note", and "Information" keys.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.alphavantage"
ALLOWED_HOSTS = ("www.alphavantage.co",)
API = "https://www.alphavantage.co/query"

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


def call_get(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
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
    for key in ("Error Message", "Note", "Information"):
        if key in result:
            sys.exit(f"error: alpha vantage {key}: {result[key]}")
    return result


def cmd_quote(args):
    result = call_get({"function": "GLOBAL_QUOTE", "symbol": args.symbol})
    quote = result.get("Global Quote") or {}
    if not quote:
        sys.exit(f"error: unknown symbol: {args.symbol}")
    out = {
        "symbol": args.symbol.upper(),
        "price": quote.get("05. price"),
        "change": quote.get("09. change"),
        "change_percent": quote.get("10. change percent"),
    }
    print(json.dumps(out, indent=2))


def cmd_daily(args):
    result = call_get(
        {"function": "TIME_SERIES_DAILY", "symbol": args.symbol, "outputsize": "compact"}
    )
    series = result.get("Time Series (Daily)") or {}
    dates = sorted(series.keys(), reverse=True)[:5]
    out = [{"date": d, "close": series[d].get("4. close")} for d in dates]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Alpha Vantage CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("quote", help="latest quote for a symbol")
    p.add_argument("--symbol", required=True)
    p.set_defaults(func=cmd_quote)

    p = sub.add_parser("daily", help="last 5 daily closes for a symbol")
    p.add_argument("--symbol", required=True)
    p.set_defaults(func=cmd_daily)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
