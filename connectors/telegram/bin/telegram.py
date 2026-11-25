#!/usr/bin/env python3
"""Minimal Telegram Bot API CLI for the muse-connectors Telegram skill.

Auth: the Bot API token travels as a URL path segment
(https://api.telegram.org/bot<token>/METHOD). This script never sees the raw
token: it builds the URL through the bundled dynamic_credentials helper,
which substitutes a surrogate the runtime swaps on approved egress, only to
api.telegram.org.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.telegram"
ALLOWED_HOSTS = ("api.telegram.org",)

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        read_json_response,
        url_with_surrogate_path_segment,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def call(method: str, payload: dict | None = None, params: dict | None = None) -> dict:
    template = "https://api.telegram.org/bot{}/" + method
    try:
        url = url_with_surrogate_path_segment(
            template, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS
        )
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if not result.get("ok"):
        sys.exit(f"error: telegram returned: {result.get('description')}")
    return result.get("result", {})


def cmd_me(_args):
    me = call("getMe")
    print(json.dumps(
        {"id": me.get("id"), "is_bot": me.get("is_bot"),
         "first_name": me.get("first_name"), "username": me.get("username")},
        indent=2))


def cmd_send(args):
    result = call("sendMessage", payload={"chat_id": args.chat_id, "text": args.text})
    print(json.dumps(
        {"ok": True, "message_id": result.get("message_id"),
         "chat_id": (result.get("chat") or {}).get("id")},
        indent=2))


def cmd_updates(args):
    updates = call("getUpdates", params={"limit": args.limit, "timeout": 0})
    out = []
    for u in updates:
        msg = u.get("message") or {}
        chat = msg.get("chat") or {}
        sender = msg.get("from") or {}
        out.append({
            "update_id": u.get("update_id"),
            "chat_id": chat.get("id"),
            "chat_type": chat.get("type"),
            "from": sender.get("username") or sender.get("first_name"),
            "text": (msg.get("text") or "")[:300],
            "date": msg.get("date"),
        })
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Telegram Bot API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("me", help="bot identity")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("send", help="send a message")
    p.add_argument("--chat-id", required=True, help="chat id (from `updates` output)")
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("updates", help="recent incoming updates")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_updates)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
