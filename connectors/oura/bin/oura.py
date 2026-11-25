#!/usr/bin/env python3
"""Minimal Oura API v2 CLI for the muse-connectors oura skill.

Auth: loads the per-user `custom.oura` credential as a surrogate via the
bundled dynamic_credentials helper. The real OAuth token never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.ouraring.com.

The Oura API is read-only: there are no write endpoints, so there is no
write risk.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.oura"
ALLOWED_HOSTS = ("api.ouraring.com",)
API = "https://api.ouraring.com"

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


def call(method: str, path: str, params: dict | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={}, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("detail", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: oura returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def date_params(args) -> dict:
    params: dict = {}
    if args.start_date:
        params["start_date"] = args.start_date
    if args.end_date:
        params["end_date"] = args.end_date
    return params


def cmd_auth(_args):
    result = call("GET", "/v2/usercollection/daily_readiness",
                  params={"limit": 1})
    print(json.dumps({"ok": True,
                      "documents": len(result.get("data", []))}, indent=2))


def _read(resource: str, args):
    params = date_params(args)
    params["limit"] = args.limit
    result = call("GET", f"/v2/usercollection/{resource}", params=params)
    docs = result.get("data", [])
    print(json.dumps(docs, indent=2))


def cmd_daily_sleep(args):
    _read("daily_sleep", args)


def cmd_sleep(args):
    _read("sleep", args)


def cmd_daily_readiness(args):
    _read("daily_readiness", args)


def cmd_workouts(args):
    _read("workout", args)


def cmd_daily_spo2(args):
    _read("daily_spo2", args)


def add_range(p):
    p.add_argument("--start-date", default=None, help="YYYY-MM-DD")
    p.add_argument("--end-date", default=None, help="YYYY-MM-DD")
    p.add_argument("--limit", type=int, default=10)


def main():
    parser = argparse.ArgumentParser(description="Oura API v2 CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the OAuth token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("daily-sleep", help="sleep scores (contributors + score)")
    add_range(p)
    p.set_defaults(func=cmd_daily_sleep)

    p = sub.add_parser("sleep", help="detailed sleep sessions")
    add_range(p)
    p.set_defaults(func=cmd_sleep)

    p = sub.add_parser("daily-readiness", help="readiness scores")
    add_range(p)
    p.set_defaults(func=cmd_daily_readiness)

    p = sub.add_parser("workouts", help="workout sessions")
    add_range(p)
    p.set_defaults(func=cmd_workouts)

    p = sub.add_parser("daily-spo2", help="blood oxygen summaries")
    add_range(p)
    p.set_defaults(func=cmd_daily_spo2)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
