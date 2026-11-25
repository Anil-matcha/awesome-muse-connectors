#!/usr/bin/env python3
"""Minimal Calendly API CLI for the muse-connectors calendly skill.

Auth: loads the per-user `custom.calendly` credential as a surrogate via the
bundled dynamic_credentials helper. The real OAuth token (or personal access
token) never touches this script: the runtime swaps the surrogate on approved
egress, only to api.calendly.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.calendly"
ALLOWED_HOSTS = ("api.calendly.com",)
API = "https://api.calendly.com"

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
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("title", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: calendly returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = call("GET", "/users/me")
    resource = result.get("resource", {})
    print(json.dumps({"ok": True, "uri": resource.get("uri"),
                      "email": resource.get("email")}, indent=2))


def cmd_scheduled_events(args):
    params = {"user": args.user, "count": args.count}
    if args.min_start_time:
        params["min_start_time"] = args.min_start_time
    if args.max_start_time:
        params["max_start_time"] = args.max_start_time
    result = call("GET", "/scheduled_events", params=params)
    events = [
        {"uri": e.get("uri"), "name": e.get("name"),
         "start_time": e.get("start_time"), "end_time": e.get("end_time"),
         "status": e.get("status")}
        for e in result.get("collection", [])
    ]
    print(json.dumps(events, indent=2))


def cmd_event_types(args):
    params = {"user": args.user, "count": args.count, "active": "true"}
    result = call("GET", "/event_types", params=params)
    types = [
        {"uri": t.get("uri"), "name": t.get("name"),
         "slug": t.get("slug"), "duration": t.get("duration"),
         "scheduling_url": t.get("scheduling_url")}
        for t in result.get("collection", [])
    ]
    print(json.dumps(types, indent=2))


def cmd_invitees(args):
    result = call("GET", f"/scheduled_events/{args.event_uuid}/invitees")
    invitees = [
        {"uri": i.get("uri"), "name": i.get("name"), "email": i.get("email"),
         "status": i.get("status")}
        for i in result.get("collection", [])
    ]
    print(json.dumps(invitees, indent=2))


def cmd_availability(args):
    params = {"user": args.user}
    result = call("GET", "/user_availability_schedules", params=params)
    schedules = [
        {"uri": s.get("uri"), "name": s.get("name"),
         "default": s.get("default")}
        for s in result.get("collection", [])
    ]
    print(json.dumps(schedules, indent=2))


def cmd_cancel(args):
    payload: dict = {}
    if args.reason:
        payload["reason"] = args.reason
    result = call("POST", f"/scheduled_events/{args.event_uuid}/cancellation",
                  payload=payload)
    resource = result.get("resource", {})
    print(json.dumps({"ok": True, "uri": resource.get("uri"),
                      "status": resource.get("status")}, indent=2))


def add_user(p):
    p.add_argument("--user", required=True,
                   help="user URI, e.g. https://api.calendly.com/users/ABC123 "
                        "(get it from `auth` or `users/me`)")


def main():
    parser = argparse.ArgumentParser(description="Calendly API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("scheduled-events", help="list scheduled events")
    add_user(p)
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--min-start-time", default=None,
                   help="ISO 8601, e.g. 2026-09-16T00:00:00Z")
    p.add_argument("--max-start-time", default=None, help="ISO 8601")
    p.set_defaults(func=cmd_scheduled_events)

    p = sub.add_parser("event-types", help="list event types")
    add_user(p)
    p.add_argument("--count", type=int, default=20)
    p.set_defaults(func=cmd_event_types)

    p = sub.add_parser("invitees", help="list invitees for an event")
    p.add_argument("--event-uuid", required=True,
                   help="the event UUID (last segment of the event URI)")
    p.set_defaults(func=cmd_invitees)

    p = sub.add_parser("availability", help="list availability schedules")
    add_user(p)
    p.set_defaults(func=cmd_availability)

    p = sub.add_parser("cancel", help="cancel a booking (confirm first)")
    p.add_argument("--event-uuid", required=True)
    p.add_argument("--reason", default=None)
    p.set_defaults(func=cmd_cancel)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
