#!/usr/bin/env python3
"""Minimal Equibles CLI for the muse-connectors equibles skill.

Auth: the API key is sent only in the `Authorization: Bearer` header, never in
the URL. On a Muse runtime the per-user `custom.equibles` credential is loaded
as a surrogate via the bundled dynamic_credentials helper, so the real key
never touches this script. Outside Muse, the key is read from the
EQUIBLES_API_KEY environment variable. Every endpoint needs a key.

Read-only by design: every call is a GET to api.equibles.com over HTTPS.
Responses are printed unchanged.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.equibles"
ENV_KEY = "EQUIBLES_API_KEY"
ALLOWED_HOSTS = ("api.equibles.com",)
API = "https://api.equibles.com/v1"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import DynamicCredentialError, add_surrogate_to_request
except ImportError:  # not on a Muse runtime: env var only
    DynamicCredentialError = Exception
    add_surrogate_to_request = None


def check_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        sys.exit(f"error: refusing request to non-allowlisted URL: {url}")


class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only if it stays on an allowlisted HTTPS host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(SameHostRedirect)


def attach_key(req: urllib.request.Request) -> str:
    """Attach the key as a Bearer token. Returns the auth mode used."""
    key = os.environ.get(ENV_KEY, "").strip()
    if any(ch.isspace() or not ch.isprintable() for ch in key):
        # Never echo the key itself in the error.
        sys.exit(f"error: {ENV_KEY} contains whitespace or control characters")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
        return "env"
    if add_surrogate_to_request is not None:
        try:
            add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
            return "muse"
        except DynamicCredentialError:
            pass
    return "none"


def call(path: str, params: dict | None = None):
    query = {k: v for k, v in (params or {}).items() if v is not None}
    url = API + path + ("?" + urllib.parse.urlencode(query) if query else "")
    check_url(url)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    if attach_key(req) == "none":
        sys.exit(
            f"error: Equibles needs an API key "
            f"(set {ENV_KEY}, or connect custom.equibles in Muse)"
        )
    try:
        with OPENER.open(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        sys.exit(f"error: equibles returned HTTP {exc.code}: {body[:400]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def emit(result) -> None:
    print(json.dumps(result, indent=2))


def ticker(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", value):
        raise argparse.ArgumentTypeError(f"not a ticker symbol: {value}")
    return value.upper()


def uuid(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", value):
        raise argparse.ArgumentTypeError(f"not a document id: {value}")
    return value


def limit(value: str) -> int:
    n = int(value)
    if not 1 <= n <= 100:
        raise argparse.ArgumentTypeError("limit must be between 1 and 100")
    return n


def q(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def cmd_status(args):
    result = call("/market/status")
    labels = {"env": f"Bearer key from {ENV_KEY}", "muse": f"Bearer key from {CREDENTIAL_NAME}"}
    print(f"auth: {labels[attach_key(urllib.request.Request(API + '/market/status'))]}", file=sys.stderr)
    emit(result)


def cmd_search(args):
    params = {"query": args.query, "documentType": args.type, "startDate": args.start,
              "endDate": args.end, "limit": args.limit}
    path = f"/stocks/{q(args.ticker)}/filings/search" if args.ticker else "/filings/search"
    emit(call(path, params))


def cmd_lines(args):
    emit(call(f"/filings/{args.document_id}/lines", {"startLine": args.start, "endLine": args.end}))


def cmd_statement(args):
    emit(call(f"/stocks/{q(args.ticker)}/financial-statements/{args.statement}",
              {"year": args.year, "period": args.period}))


def cmd_call(args):
    emit(call(f"/stocks/{q(args.ticker)}/earnings-calls/{args.year}/{args.quarter}"))


def cmd_insiders(args):
    params = {"transactionType": args.type, "startDate": args.start, "endDate": args.end,
              "limit": args.limit}
    emit(call(f"/stocks/{q(args.ticker)}/insider-transactions", params))


def cmd_holders(args):
    emit(call(f"/stocks/{q(args.ticker)}/institutional-holders", {"limit": args.limit}))


def cmd_congress(args):
    params = {"ticker": args.ticker, "transactionType": args.type, "startDate": args.start,
              "endDate": args.end, "limit": args.limit}
    emit(call("/congress/trades", params))


def cmd_prices(args):
    params = {"startDate": args.start, "endDate": args.end, "limit": args.limit}
    emit(call(f"/stocks/{q(args.ticker)}/prices", params))


def main():
    parser = argparse.ArgumentParser(description="Equibles CLI (muse-connectors, read-only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="market status; confirms the key works")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("search", help="search SEC filings and earnings call transcripts")
    p.add_argument("query")
    p.add_argument("--ticker", type=ticker, help="only this company's documents")
    p.add_argument("--type", help="document type, e.g. 10-K, 10-Q, 8-K")
    p.add_argument("--start", help="earliest filing date YYYY-MM-DD")
    p.add_argument("--end", help="latest filing date YYYY-MM-DD")
    p.add_argument("--limit", type=limit, help="excerpts to return (1-100, default 5)")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("lines", help="read numbered lines of one filing or transcript")
    p.add_argument("document_id", type=uuid)
    p.add_argument("start", type=int, help="first line (1-based)")
    p.add_argument("end", type=int, help="last line (at most 500 lines per call)")
    p.set_defaults(func=cmd_lines)

    p = sub.add_parser("statement", help="income, balance or cash-flow statement from SEC XBRL")
    p.add_argument("ticker", type=ticker)
    p.add_argument("statement", choices=["income", "balance", "cashflow"])
    p.add_argument("--year", type=int, help="fiscal year (omit with --period for the latest)")
    p.add_argument("--period", choices=["FY", "Q1", "Q2", "Q3", "Q4"])
    p.set_defaults(func=cmd_statement)

    p = sub.add_parser("call", help="earnings call record for a fiscal quarter")
    p.add_argument("ticker", type=ticker)
    p.add_argument("year", type=int, help="fiscal year")
    p.add_argument("quarter", type=int, choices=[1, 2, 3, 4], help="fiscal quarter")
    p.set_defaults(func=cmd_call)

    p = sub.add_parser("insiders", help="Form 4 insider transactions, newest first")
    p.add_argument("ticker", type=ticker)
    p.add_argument("--type", help="Buy, Sell, Award, Exercise, Gift, ...")
    p.add_argument("--start", help="from date YYYY-MM-DD")
    p.add_argument("--end", help="to date YYYY-MM-DD")
    p.add_argument("--limit", type=limit)
    p.set_defaults(func=cmd_insiders)

    p = sub.add_parser("holders", help="13F institutional holders, latest quarter")
    p.add_argument("ticker", type=ticker)
    p.add_argument("--limit", type=limit)
    p.set_defaults(func=cmd_holders)

    p = sub.add_parser("congress", help="congressional stock trades for a ticker, newest first")
    p.add_argument("--ticker", type=ticker, required=True)
    p.add_argument("--type", choices=["Purchase", "Sale"])
    p.add_argument("--start", help="from transaction date YYYY-MM-DD (default: 1 year ago)")
    p.add_argument("--end", help="to transaction date YYYY-MM-DD")
    p.add_argument("--limit", type=limit)
    p.set_defaults(func=cmd_congress)

    p = sub.add_parser("prices", help="daily end-of-day prices")
    p.add_argument("ticker", type=ticker)
    p.add_argument("--start", help="from date YYYY-MM-DD")
    p.add_argument("--end", help="to date YYYY-MM-DD")
    p.add_argument("--limit", type=limit)
    p.set_defaults(func=cmd_prices)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
