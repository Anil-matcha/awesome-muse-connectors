#!/usr/bin/env python3
"""Minimal Zep API CLI for the muse-connectors zep skill.

Auth: loads the per-user `custom.zep` credential as a surrogate via the
bundled dynamic_credentials helper, then sends it verbatim as
`Authorization: Api-Key <surrogate>` (Zep's nonstandard scheme: capital A,
hyphen, not Bearer). The real key never touches this script: the runtime
swaps the surrogate on approved egress, only to api.getzep.com.

Pinned to API v2 (threads). Zep extracts facts and graph entities from
messages asynchronously, so allow a few minutes before `context` shows
freshly added messages.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.zep"
ALLOWED_HOSTS = ("api.getzep.com",)
API = "https://api.getzep.com/api/v2"

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
    headers = {"Accept": "application/json"}
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
    req.add_header("Authorization", f"Api-Key {surrogate}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("error", body.get("detail", str(exc))))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: zep returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(args):
    # Cheap live check: read a thread's distilled context. Without a thread
    # id we can only verify the credential resolves.
    if args.thread_id:
        result = call("GET", f"/threads/{args.thread_id}/context")
        print(json.dumps({"ok": True, "live": True,
                          "thread_id": args.thread_id,
                          "facts": len(result.get("facts", []) or [])}, indent=2))
    else:
        try:
            dynamic_credential_entry(CREDENTIAL_NAME)
        except DynamicCredentialError as exc:
            sys.exit(f"error: credential problem: {exc}")
        print(json.dumps({"ok": True, "live": False,
                          "note": "credential resolves; pass --thread-id for a live check"},
                         indent=2))


def cmd_user_create(args):
    payload = {"user_id": args.user_id}
    if args.email:
        payload["email"] = args.email
    if args.first_name:
        payload["first_name"] = args.first_name
    if args.last_name:
        payload["last_name"] = args.last_name
    result = call("POST", "/users", payload=payload)
    print(json.dumps({"ok": True, "user_id": result.get("user_id")}, indent=2))


def cmd_thread_create(args):
    payload = {}
    if args.thread_id:
        payload["thread_id"] = args.thread_id
    if args.user_id:
        payload["user_id"] = args.user_id
    result = call("POST", "/threads", payload=payload)
    print(json.dumps({"ok": True, "thread_id": result.get("thread_id")}, indent=2))


def cmd_message_add(args):
    payload = {"messages": [{"role": args.role, "content": args.content}]}
    result = call("POST", f"/threads/{args.thread_id}/messages", payload=payload)
    print(json.dumps({"ok": True, "thread_id": args.thread_id,
                      "note": "fact extraction is async; allow minutes before reading context"},
                     indent=2))


def cmd_context(args):
    result = call("GET", f"/threads/{args.thread_id}/context")
    print(json.dumps(result, indent=2))


def cmd_messages(args):
    params = {}
    if args.limit:
        params["limit"] = args.limit
    result = call("GET", f"/threads/{args.thread_id}/messages", params=params)
    msgs = result.get("messages", result) if isinstance(result, dict) else result
    if isinstance(msgs, list):
        out = [
            {"role": m.get("role"), "content": (m.get("content") or "")[:800],
             "created_at": m.get("created_at")}
            for m in msgs
        ]
        print(json.dumps(out, indent=2))
    else:
        print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Zep API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key (live check with --thread-id)")
    p.add_argument("--thread-id", default=None)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("user-create", help="create a user container (confirm first)")
    p.add_argument("--user-id", required=True)
    p.add_argument("--email", default=None)
    p.add_argument("--first-name", default=None)
    p.add_argument("--last-name", default=None)
    p.set_defaults(func=cmd_user_create)

    p = sub.add_parser("thread-create", help="create a thread (confirm first)")
    p.add_argument("--thread-id", default=None)
    p.add_argument("--user-id", default=None)
    p.set_defaults(func=cmd_thread_create)

    p = sub.add_parser("message-add", help="append a message; zep extracts facts async (confirm first)")
    p.add_argument("--thread-id", required=True)
    p.add_argument("--role", default="user")
    p.add_argument("--content", required=True)
    p.set_defaults(func=cmd_message_add)

    p = sub.add_parser("context", help="distilled facts for a thread")
    p.add_argument("--thread-id", required=True)
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("messages", help="conversation history of a thread")
    p.add_argument("--thread-id", required=True)
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_messages)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
