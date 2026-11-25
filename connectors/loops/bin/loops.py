#!/usr/bin/env python3
"""Minimal Loops API CLI for the muse-connectors loops skill.

Auth: loads the per-user `custom.loops` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
app.loops.so.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.loops"
ALLOWED_HOSTS = ("app.loops.so",)
API = "https://app.loops.so/api/v1"

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
            msg = body.get("message", body.get("error", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: loops returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def parse_kv(pairs) -> dict:
    out = {}
    for pair in pairs or []:
        if "=" not in pair:
            sys.exit(f"error: expected KEY=VALUE, got {pair!r}")
        key, value = pair.split("=", 1)
        out[key] = value
    return out


def cmd_auth(_args):
    result = call("GET", "/api-key")
    print(json.dumps({"ok": True,
                      "message": result.get("message")}, indent=2))


def cmd_find(args):
    result = call("GET", "/contacts/find", params={"email": args.email})
    print(json.dumps(result, indent=2))


def cmd_create(args):
    payload = {"email": args.email}
    payload.update(parse_kv(args.field))
    result = call("POST", "/contacts/create", payload=payload)
    print(json.dumps(result, indent=2))


def cmd_upsert(args):
    # Loops documents PUT /contacts/update as the upsert path.
    payload = {"email": args.email}
    payload.update(parse_kv(args.field))
    result = call("PUT", "/contacts/update", payload=payload)
    print(json.dumps(result, indent=2))


def cmd_event(args):
    payload = {"email": args.email, "eventName": args.name,
               "eventProperties": parse_kv(args.prop)}
    result = call("POST", "/events/send", payload=payload)
    print(json.dumps(result, indent=2))


def cmd_send_email(args):
    payload = {"email": args.email, "transactionalId": args.template_id,
               "dataVariables": parse_kv(args.var)}
    result = call("POST", "/transactional", payload=payload)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Loops API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("find", help="look up a contact by email")
    p.add_argument("--email", required=True)
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("create", help="add a contact (confirm first)")
    p.add_argument("--email", required=True)
    p.add_argument("--field", action="append", default=[],
                   help="contact field as KEY=VALUE (repeatable)")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("upsert", help="create or update a contact (confirm first)")
    p.add_argument("--email", required=True)
    p.add_argument("--field", action="append", default=[],
                   help="contact field as KEY=VALUE (repeatable)")
    p.set_defaults(func=cmd_upsert)

    p = sub.add_parser("event", help="fire an event for a contact (confirm first)")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True, help="event name")
    p.add_argument("--prop", action="append", default=[],
                   help="event property as KEY=VALUE (repeatable)")
    p.set_defaults(func=cmd_event)

    p = sub.add_parser("send-email",
                       help="send a transactional email (confirm first)")
    p.add_argument("--email", required=True)
    p.add_argument("--template-id", required=True)
    p.add_argument("--var", action="append", default=[],
                   help="template variable as KEY=VALUE (repeatable)")
    p.set_defaults(func=cmd_send_email)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
