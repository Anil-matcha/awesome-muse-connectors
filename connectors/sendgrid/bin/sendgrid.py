#!/usr/bin/env python3
"""Minimal SendGrid v3 API CLI for the muse-connectors SendGrid skill.

Auth: loads the per-user `custom.sendgrid` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.sendgrid.com.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.sendgrid"
ALLOWED_HOSTS = ("api.sendgrid.com",)
API = "https://api.sendgrid.com/v3"

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
         payload: dict | None = None, expect_empty: bool = False):
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
            if expect_empty or resp.status == 202:
                return {"ok": True, "status": resp.status,
                        "message_id": resp.headers.get("X-Message-Id")}
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            errors = body.get("errors", [str(exc)])
            msg = "; ".join(e.get("message", str(e)) for e in errors)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: sendgrid returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = call("GET", "/user/profile")
    print(json.dumps({"ok": True, "type": result.get("type"),
                      "username": result.get("username")}, indent=2))


def cmd_send(args):
    payload = {
        "personalizations": [{
            "to": [{"email": t.strip()} for t in args.to.split(",")],
            "subject": args.subject,
        }],
        "from": {"email": args.from_},
        "content": [{"type": "text/plain", "value": args.text}],
    }
    if args.name:
        payload["from"]["name"] = args.name
    if args.html:
        payload["content"].append({"type": "text/html", "value": args.html})
    result = call("POST", "/mail/send", payload=payload)
    print(json.dumps(result, indent=2))


def cmd_stats(args):
    start = args.start_date or (
        datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    result = call("GET", "/stats",
                  params={"start_date": start, "aggregated_by": "day"})
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="SendGrid v3 API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("send", help="send an email (confirm first)")
    p.add_argument("--from", dest="from_", required=True,
                   help="sender address on a verified SendGrid domain")
    p.add_argument("--name", default=None, help="sender display name")
    p.add_argument("--to", required=True,
                   help="recipient address(es), comma-separated")
    p.add_argument("--subject", required=True)
    p.add_argument("--text", required=True, help="plain-text body")
    p.add_argument("--html", default=None, help="HTML body")
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("stats", help="email stats by day")
    p.add_argument("--start-date", default=None,
                   help="YYYY-MM-DD, defaults to 7 days ago")
    p.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
