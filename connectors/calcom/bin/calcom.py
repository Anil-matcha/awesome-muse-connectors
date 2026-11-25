#!/usr/bin/env python3
"""Minimal Cal.com API CLI for the muse-connectors Cal.com skill.

Auth: loads the per-user `custom.calcom` credential as a surrogate via the
bundled dynamic_credentials helper. Cal.com v2 personal API keys are sent as
the `apiKey` query parameter (Bearer is reserved for OAuth tokens), so the CLI
uses the helper's query-param placement: the runtime swaps the surrogate into
the URL on approved egress, only to api.cal.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.calcom"
ALLOWED_HOSTS = ("api.cal.com",)
API = "https://api.cal.com/v2"
API_VERSION = "2024-08-13"

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


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        url = url_with_surrogate_query_param(
            url, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    data = None
    headers = {"cal-api-version": API_VERSION}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", {}).get("message", str(exc)) \
                if isinstance(body.get("error"), dict) else body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: cal.com returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if result.get("status") == "error":
        sys.exit(f"error: cal.com: {json.dumps(result.get('error'))}")
    return result.get("data", result)


def cmd_auth(_args):
    me = call("GET", "/me")
    print(json.dumps({"ok": True, "id": me.get("id"), "email": me.get("email"),
                      "name": me.get("name")}, indent=2))


def cmd_bookings(args):
    params = {"take": args.limit}
    if args.status:
        params["status"] = args.status
    bookings = call("GET", "/bookings", params=params)
    out = [
        {"uid": b.get("uid"), "title": b.get("title"), "status": b.get("status"),
         "start": b.get("start"), "end": b.get("end"),
         "attendees": [a.get("email") for a in b.get("attendees", [])]}
        for b in (bookings if isinstance(bookings, list) else [])
    ]
    print(json.dumps(out, indent=2))


def cmd_event_types(args):
    types = call("GET", "/event-types", params={"take": args.limit})
    out = [
        {"id": t.get("id"), "title": t.get("title"), "slug": t.get("slug"),
         "length": t.get("length")}
        for t in (types if isinstance(types, list) else [])
    ]
    print(json.dumps(out, indent=2))


def cmd_create_booking(args):
    payload = {
        "eventTypeId": args.event_type_id,
        "start": args.start,
        "attendee": {"name": args.name, "email": args.email,
                     "timeZone": args.timezone},
    }
    booking = call("POST", "/bookings", payload=payload)
    print(json.dumps({"ok": True, "uid": booking.get("uid"),
                      "status": booking.get("status")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Cal.com API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("bookings", help="list bookings")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--status", default=None,
                   help="filter: upcoming, past, cancelled, ...")
    p.set_defaults(func=cmd_bookings)

    p = sub.add_parser("event-types", help="list event types")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_event_types)

    p = sub.add_parser("create-booking", help="create a booking (confirm first)")
    p.add_argument("--event-type-id", type=int, required=True)
    p.add_argument("--start", required=True,
                   help="ISO start time, e.g. 2026-09-20T10:00:00Z")
    p.add_argument("--name", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--timezone", default="America/Los_Angeles")
    p.set_defaults(func=cmd_create_booking)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
