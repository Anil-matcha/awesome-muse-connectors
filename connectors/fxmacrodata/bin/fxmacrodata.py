#!/usr/bin/env python3
"""Minimal FXMacroData CLI for the muse-connectors fxmacrodata skill.

Auth: the key is sent only in the `X-API-Key` header, never in the URL.
On a Muse runtime the per-user `custom.fxmacrodata` credential is loaded as a
surrogate via the bundled dynamic_credentials helper, so the real key never
touches this script. Outside Muse, the key is read from the
FXMACRODATA_API_KEY environment variable. With neither, requests go out
without a key: USD data still works (15-minute delay, last 90 days of
history); other currencies and FX rates return HTTP 401 api_key_required.

Read-only by design: every call is a GET to api.fxmacrodata.com over HTTPS.
Responses are printed unchanged. When a response carries `freemium_delay`
or `freemium_window`, a short notice is also written to stderr.
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
CREDENTIAL_NAME = "custom.fxmacrodata"
ENV_KEY = "FXMACRODATA_API_KEY"
ALLOWED_HOSTS = ("api.fxmacrodata.com",)
API = "https://api.fxmacrodata.com/v1"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import DynamicCredentialError, add_surrogate_to_request
except ImportError:  # not on a Muse runtime: env var or keyless only
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
    """Attach the key to the X-API-Key header. Returns the auth mode used."""
    key = os.environ.get(ENV_KEY, "").strip()
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


def call(path: str, params: dict | None = None, need_key: bool = False) -> dict:
    query = {k: v for k, v in (params or {}).items() if v is not None}
    url = API + path + ("?" + urllib.parse.urlencode(query) if query else "")
    check_url(url)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    mode = attach_key(req)
    if need_key and mode == "none":
        sys.exit(
            f"error: this command needs an FXMacroData API key "
            f"(set {ENV_KEY}, or connect custom.fxmacrodata in Muse)"
        )
    try:
        with OPENER.open(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        sys.exit(f"error: fxmacrodata returned HTTP {exc.code}: {body[:400]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    notice(result)
    return result


def notice(result) -> None:
    if not isinstance(result, dict):
        return
    delay = result.get("freemium_delay")
    if isinstance(delay, dict) and delay.get("applied"):
        withheld = delay.get("withheld_count") or 0
        print(
            f"notice: freemium_delay: data is {delay.get('delay_minutes', 15)} minutes "
            f"delayed (cutoff {delay.get('cutoff_iso')}, {withheld} release(s) withheld)",
            file=sys.stderr,
        )
    window = result.get("freemium_window")
    if isinstance(window, dict) and window.get("applied"):
        print(
            f"notice: freemium_window: history limited to {window.get('max_days')} days "
            f"(from {window.get('cutoff_date')})",
            file=sys.stderr,
        )


def emit(result) -> None:
    print(json.dumps(result, indent=2))


def currency(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z]{3}", value):
        raise argparse.ArgumentTypeError(f"not a 3-letter currency code: {value}")
    return value.upper()


def slug(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9_]+", value):
        raise argparse.ArgumentTypeError(f"not an indicator slug: {value}")
    return value


def limit(value: str) -> int:
    n = int(value)
    if not 1 <= n <= 100:
        raise argparse.ArgumentTypeError("limit must be between 1 and 100")
    return n


def cmd_status(args):
    result = call("/health")
    labels = {
        "env": f"X-API-Key from {ENV_KEY}",
        "muse": f"X-API-Key from {CREDENTIAL_NAME}",
        "none": "no key (USD only, 15-minute delay, 90-day history)",
    }
    print(f"auth: {labels[attach_key(urllib.request.Request(API + '/health'))]}", file=sys.stderr)
    emit(result)


def cmd_catalogue(args):
    emit(call(f"/data_catalogue/{args.currency}"))


def cmd_history(args):
    params = {"start_date": args.start, "end_date": args.end, "limit": args.limit}
    emit(call(f"/announcements/{args.currency}/{args.indicator}", params))


def cmd_calendar(args):
    params = {"indicator": args.indicator, "start_date": args.start, "end_date": args.end}
    emit(call(f"/calendar/{args.currency}", params))


def cmd_forex(args):
    params = {"start_date": args.start, "end_date": args.end, "limit": args.limit}
    emit(call(f"/forex/{args.base}/{args.quote}", params, need_key=True))


def main():
    parser = argparse.ArgumentParser(description="FXMacroData CLI (muse-connectors, read-only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="ping the API and show which auth mode is in use")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("catalogue", help="indicators available for a currency")
    p.add_argument("currency", type=currency)
    p.set_defaults(func=cmd_catalogue)

    p = sub.add_parser("history", help="release history for one indicator")
    p.add_argument("currency", type=currency)
    p.add_argument("indicator", type=slug)
    p.add_argument("--start", help="start date YYYY-MM-DD")
    p.add_argument("--end", help="end date YYYY-MM-DD")
    p.add_argument("--limit", type=limit, help="rows to return, most recent first (1-100)")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("calendar", help="upcoming release dates for a currency")
    p.add_argument("currency", type=currency)
    p.add_argument("--indicator", type=slug, help="only this indicator")
    p.add_argument("--start", help="start date YYYY-MM-DD")
    p.add_argument("--end", help="end date YYYY-MM-DD")
    p.set_defaults(func=cmd_calendar)

    p = sub.add_parser("forex", help="daily FX spot rates (API key required)")
    p.add_argument("base", type=currency)
    p.add_argument("quote", type=currency)
    p.add_argument("--start", help="start date YYYY-MM-DD")
    p.add_argument("--end", help="end date YYYY-MM-DD")
    p.add_argument("--limit", type=limit, help="rows to return (1-100, default 20)")
    p.set_defaults(func=cmd_forex)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
