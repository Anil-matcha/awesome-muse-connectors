#!/usr/bin/env python3
"""Minimal Postmark API CLI for the muse-connectors Postmark skill.

Auth: loads the per-user `custom.postmark` credential as a surrogate via the
bundled dynamic_credentials helper. Postmark authenticates with the
`X-Postmark-Server-Token` header whose value is the raw server token; the
placement is resolved by the helper from the credential config. The real token
never touches this script: the runtime swaps the surrogate on approved egress,
only to api.postmarkapp.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.postmark"
ALLOWED_HOSTS = ("api.postmarkapp.com",)
API = "https://api.postmarkapp.com"

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
    headers = {"Accept": "application/json"}
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
            msg = f"{body.get('ErrorCode')}: {body.get('Message', str(exc))}"
        except Exception:
            msg = str(exc)
        sys.exit(f"error: postmark returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = call("GET", "/server")
    print(json.dumps({"ok": True, "id": result.get("ID"),
                      "name": result.get("Name"),
                      "api_tokens": result.get("ApiTokens")}, indent=2))


def cmd_send(args):
    payload = {
        "From": args.from_,
        "To": args.to,
        "Subject": args.subject,
        "TextBody": args.text,
        "MessageStream": args.stream,
    }
    if args.html:
        payload["HtmlBody"] = args.html
    result = call("POST", "/email", payload=payload)
    print(json.dumps({"ok": result.get("ErrorCode") == 0,
                      "message_id": result.get("MessageID"),
                      "submitted_at": result.get("SubmittedAt")}, indent=2))


def cmd_messages(args):
    result = call("GET", "/messages/outbound",
                  params={"count": args.limit, "offset": 0})
    messages = [
        {"message_id": m.get("MessageID"), "to": m.get("Recipients"),
         "subject": m.get("Subject"), "status": m.get("Status"),
         "received_at": m.get("ReceivedAt")}
        for m in result.get("Messages", [])
    ]
    print(json.dumps(messages, indent=2))


def cmd_bounces(args):
    result = call("GET", "/bounces",
                  params={"count": args.limit, "offset": 0})
    bounces = [
        {"email": b.get("Email"), "type": b.get("Type"),
         "description": b.get("Description"), "bounced_at": b.get("BouncedAt")}
        for b in result.get("Bounces", [])
    ]
    print(json.dumps(bounces, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Postmark API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the server token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("send", help="send an email (confirm first)")
    p.add_argument("--from", dest="from_", required=True,
                   help="sender address on a verified Postmark domain/signature")
    p.add_argument("--to", required=True,
                   help="recipient address(es), comma-separated")
    p.add_argument("--subject", required=True)
    p.add_argument("--text", required=True, help="plain-text body")
    p.add_argument("--html", default=None, help="HTML body")
    p.add_argument("--stream", default="outbound",
                   help="message stream: outbound (transactional) or broadcast")
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("messages", help="recent outbound messages")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_messages)

    p = sub.add_parser("bounces", help="recent bounces")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_bounces)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
