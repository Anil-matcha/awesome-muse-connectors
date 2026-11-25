#!/usr/bin/env python3
"""Minimal Resend API CLI for the muse-connectors Resend skill.

Auth: loads the per-user `custom.resend` credential as a surrogate via the
bundled dynamic_credentials helper. The real key never touches this script:
the runtime swaps the surrogate on approved egress, only to api.resend.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.resend"
ALLOWED_HOSTS = ("api.resend.com",)
API = "https://api.resend.com"

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


def call(method: str, path: str, payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: resend returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    return result


def cmd_send(args):
    payload = {"from": args.from_, "to": [t.strip() for t in args.to.split(",")],
               "subject": args.subject, "text": args.text}
    result = call("POST", "/emails", payload)
    print(json.dumps({"id": result.get("id")}, indent=2))


def cmd_get(args):
    result = call("GET", f"/emails/{args.id}")
    print(json.dumps({
        "id": result.get("id"),
        "from": result.get("from"),
        "to": result.get("to"),
        "subject": result.get("subject"),
        "status": result.get("last_event"),
        "created_at": result.get("created_at"),
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Resend API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("send", help="send an email")
    p.add_argument("--from", dest="from_", required=True,
                   help="sender address on a verified Resend domain")
    p.add_argument("--to", required=True, help="recipient address(es), comma-separated")
    p.add_argument("--subject", required=True)
    p.add_argument("--text", required=True, help="plain-text body")
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("get", help="check delivery status of a sent email")
    p.add_argument("--id", required=True, help="email id returned by send")
    p.set_defaults(func=cmd_get)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
