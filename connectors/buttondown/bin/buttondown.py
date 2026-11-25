#!/usr/bin/env python3
"""Minimal Buttondown API CLI for the muse-connectors buttondown skill.

Auth: header `Authorization: Token <key>` verbatim (never Bearer). Loads the
per-user `custom.buttondown` credential as a surrogate via the bundled
dynamic_credentials helper. The real API key never touches this script: the
runtime swaps the surrogate on approved egress, only to api.buttondown.com.

Sending is gated: `email-create` stages a draft by default; only `--send`
sends to the whole list (confirm with the user first).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.buttondown"
ALLOWED_HOSTS = ("api.buttondown.com",)
API = "https://api.buttondown.com/v1"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        dynamic_credential_entry,
        ensure_allowed_url,
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
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        surrogate = dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    # Exact scheme: `Authorization: Token <key>` (NOT Bearer).
    req.add_header("Authorization", f"Token {surrogate}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("detail", body.get("message", body.get("error", str(exc))))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: buttondown returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def list_items(result: dict) -> list:
    if not isinstance(result, dict):
        return []
    items = result.get("results", result.get("data", []))
    return items if isinstance(items, list) else []


def cmd_auth(_args):
    result = call("GET", "/subscribers", params={"limit": 1})
    print(json.dumps({"ok": True, "subscribers": len(list_items(result))},
                     indent=2))


def cmd_subscribers(args):
    result = call("GET", "/subscribers", params={"limit": args.limit})
    subs = [
        {"id": s.get("id"), "email": s.get("email"),
         "type": s.get("type"), "notes": s.get("notes"),
         "creation_date": s.get("creation_date")}
        for s in list_items(result)
    ]
    print(json.dumps(subs, indent=2))


def cmd_subscriber_add(args):
    payload = {"email": args.email}
    if args.notes:
        payload["notes"] = args.notes
    if args.json:
        try:
            payload.update(json.loads(args.json))
        except json.JSONDecodeError as exc:
            sys.exit(f"error: --json is not valid JSON: {exc}")
    result = call("POST", "/subscribers", payload=payload)
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "email": result.get("email")}, indent=2))


def cmd_emails(args):
    result = call("GET", "/emails", params={"limit": args.limit})
    emails = [
        {"id": e.get("id"), "subject": e.get("subject"),
         "status": e.get("status"), "publish_date": e.get("publish_date")}
        for e in list_items(result)
    ]
    print(json.dumps(emails, indent=2))


def cmd_email_create(args):
    payload = {"subject": args.subject, "body": args.body}
    if args.json:
        try:
            payload.update(json.loads(args.json))
        except json.JSONDecodeError as exc:
            sys.exit(f"error: --json is not valid JSON: {exc}")
    # Draft by default; only --send pushes to the whole list.
    payload["status"] = "sent" if args.send else "draft"
    result = call("POST", "/emails", payload=payload)
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "status": result.get("status", payload["status"])},
                     indent=2))


def main():
    parser = argparse.ArgumentParser(description="Buttondown API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("subscribers", help="list subscribers")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_subscribers)

    p = sub.add_parser("subscriber-add", help="add a subscriber (confirm first)")
    p.add_argument("--email", required=True)
    p.add_argument("--notes", default=None)
    p.add_argument("--json", default=None,
                   help="extra subscriber fields as a JSON object")
    p.set_defaults(func=cmd_subscriber_add)

    p = sub.add_parser("emails", help="list emails (drafts and sent)")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_emails)

    p = sub.add_parser("email-create", help="create an email draft (confirm before --send)")
    p.add_argument("--subject", required=True)
    p.add_argument("--body", required=True, help="email body (markdown)")
    p.add_argument("--send", action="store_true",
                   help="send to the whole list NOW (confirmation-gated)")
    p.add_argument("--json", default=None,
                   help="extra email fields as a JSON object")
    p.set_defaults(func=cmd_email_create)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
