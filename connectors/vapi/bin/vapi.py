#!/usr/bin/env python3
"""Vapi voice-AI API CLI for the muse-connectors vapi skill.

Auth: loads the per-user `custom.vapi` credential as a surrogate via the
bundled dynamic_credentials helper. Vapi uses an API key sent as
Authorization: Bearer. The real key never touches this script: the runtime
swaps the surrogate on approved egress, only to api.vapi.ai.

Safety: outbound calls are HIGH actuations (each call dials a real phone
number and costs money) and require an exact --confirm string echoed by the
CLI on every call. Default to test phone numbers; a production number is
always an explicit, named choice in the confirmation string.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.vapi"
ALLOWED_HOSTS = ("api.vapi.ai",)
BASE = "https://api.vapi.ai"
CONNECT_GUIDANCE = (
    "not connected: create a Vapi API key (Vapi dashboard > API keys) and "
    "collect it via the secure credential flow "
    "(credentials.request_api_access) as `custom.vapi`, then retry."
)

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
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        if "missing" in str(exc) or "surrogate" in str(exc):
            sys.exit(CONNECT_GUIDANCE)
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            msg = body[:500]
        except Exception:
            msg = str(exc)
        sys.exit(f"error: vapi returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def limit_param(limit: int) -> str:
    return urllib.parse.urlencode({"limit": limit})


def cmd_auth(args):
    call("GET", f"/assistant?{limit_param(1)}")
    print(json.dumps({"ok": True,
                      "note": "credential accepted"}, indent=2))


def cmd_assistants(args):
    result = call("GET", f"/assistant?{limit_param(args.limit)}")
    items = result if isinstance(result, list) else result.get("data", [])
    out = [{"id": a.get("id"), "name": a.get("name"),
            "createdAt": a.get("createdAt"),
            "voice": (a.get("voice") or {}).get("provider"),
            "model": (a.get("model") or {}).get("model")}
           for a in items]
    print(json.dumps(out, indent=2))


def cmd_assistant_get(args):
    result = call("GET", f"/assistant/{args.assistant_id}")
    a = result.get("assistant", result)
    print(json.dumps({"id": a.get("id"), "name": a.get("name"),
                      "firstMessage": a.get("firstMessage"),
                      "voice": a.get("voice"), "model": a.get("model"),
                      "createdAt": a.get("createdAt")}, indent=2))


def cmd_phone_numbers(args):
    result = call("GET", f"/phone-number?{limit_param(args.limit)}")
    items = result if isinstance(result, list) else result.get("data", [])
    out = [{"id": n.get("id"), "number": n.get("number"),
            "provider": n.get("provider"),
            "assistantId": n.get("assistantId")}
           for n in items]
    print(json.dumps(out, indent=2))


def cmd_call_create(args):
    expected = (f"place outbound call from {args.phone_number_id} "
                f"to {args.customer_number}")
    need_confirm(
        args, expected,
        "an outbound call dials a REAL phone number and costs money. "
        "Default to a test phone number unless the user explicitly chose "
        "a production number.")
    payload = {
        "assistantId": args.assistant_id,
        "phoneNumberId": args.phone_number_id,
        "customer": {"number": args.customer_number},
    }
    result = call("POST", "/call", payload)
    c = result.get("call", result)
    print(json.dumps({"ok": True, "call_id": c.get("id"),
                      "status": c.get("status"),
                      "phoneNumberId": c.get("phoneNumberId"),
                      "customer": (c.get("customer") or {}).get("number")},
                     indent=2))


def cmd_call_get(args):
    result = call("GET", f"/call/{args.call_id}")
    c = result.get("call", result)
    print(json.dumps({"id": c.get("id"), "status": c.get("status"),
                      "assistantId": c.get("assistantId"),
                      "phoneNumberId": c.get("phoneNumberId"),
                      "customer": c.get("customer"),
                      "startedAt": c.get("startedAt"),
                      "endedAt": c.get("endedAt")}, indent=2))


def cmd_call_list(args):
    result = call("GET", f"/call?{limit_param(args.limit)}")
    items = result if isinstance(result, list) else result.get("data", [])
    out = [{"id": c.get("id"), "status": c.get("status"),
            "assistantId": c.get("assistantId"),
            "phoneNumberId": c.get("phoneNumberId"),
            "startedAt": c.get("startedAt"), "endedAt": c.get("endedAt")}
           for c in items]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Vapi voice-AI API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("assistants", help="list assistants")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_assistants)

    p = sub.add_parser("assistant-get", help="retrieve one assistant")
    p.add_argument("--assistant-id", required=True)
    p.set_defaults(func=cmd_assistant_get)

    p = sub.add_parser("phone-numbers", help="list phone numbers")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_phone_numbers)

    p = sub.add_parser("call-create",
                       help="place an outbound call (HIGH, costs money)")
    p.add_argument("--assistant-id", required=True)
    p.add_argument("--phone-number-id", required=True,
                   help="the Vapi number the call comes from; use a test "
                        "number unless production was explicitly chosen")
    p.add_argument("--customer-number", required=True,
                   help="E.164 number to dial, e.g. +14155551234")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_call_create)

    p = sub.add_parser("call-get", help="retrieve one call")
    p.add_argument("--call-id", required=True)
    p.set_defaults(func=cmd_call_get)

    p = sub.add_parser("call-list", help="list calls")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_call_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
