#!/usr/bin/env python3
"""Minimal Slack Web API CLI for the muse-connectors Slack skill.

Auth: loads the per-user `custom.slack` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to slack.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.slack"
ALLOWED_HOSTS = ("slack.com",)
API = "https://slack.com/api"

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


def call_raw(method: str, params: dict | None = None, payload: dict | None = None) -> dict:
    url = API + "/" + method
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        add_surrogate_to_request(
            req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS
        )
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def call(method: str, params: dict | None = None, payload: dict | None = None) -> dict:
    result = call_raw(method, params=params, payload=payload)
    if not result.get("ok"):
        sys.exit(f"error: slack returned {result.get('error')}: {json.dumps(result)}")
    return result


def cmd_auth(_args):
    result = call("auth.test")
    print(json.dumps({"ok": True, "team": result.get("team"), "user": result.get("user")}, indent=2))


def cmd_channels(args):
    result = call(
        "conversations.list",
        params={"types": "public_channel,private_channel", "limit": args.limit,
                "exclude_archived": "true"},
    )
    channels = [
        {"id": c["id"], "name": c.get("name"), "purpose": (c.get("purpose") or {}).get("value", "")}
        for c in result.get("channels", [])
    ]
    print(json.dumps(channels, indent=2))


def cmd_history(args):
    result = call(
        "conversations.history",
        params={"channel": args.channel, "limit": args.limit},
    )
    messages = [
        {"user": m.get("user"), "text": m.get("text"), "ts": m.get("ts")}
        for m in result.get("messages", [])
    ]
    print(json.dumps(messages, indent=2))


def cmd_post(args):
    result = call("chat.postMessage", payload={"channel": args.channel, "text": args.text})
    print(json.dumps({"ok": True, "channel": result.get("channel"), "ts": result.get("ts")}, indent=2))


def cmd_users(args):
    result = call("users.list", params={"limit": args.limit})
    users = [
        {"id": u["id"], "name": u.get("name"), "real_name": u.get("real_name"), "deleted": u.get("deleted")}
        for u in result.get("members", [])
        if not u.get("deleted")
    ]
    print(json.dumps(users, indent=2))


def cmd_search(args):
    result = call_raw("search.messages", params={"query": args.query, "count": args.count})
    if not result.get("ok"):
        if result.get("error") in ("missing_scope", "not_allowed_token_type"):
            sys.exit(
                "error: search needs the `search:read` scope, which Slack grants to user "
                "tokens only, never bot tokens. Add `search:read` under User Token Scopes in "
                "your Slack app (api.slack.com/apps -> OAuth & Permissions), then reconnect. "
                "See this skill's Auth section for details."
            )
        sys.exit(f"error: slack returned {result.get('error')}: {json.dumps(result)}")
    matches = (result.get("messages") or {}).get("matches", [])
    out = [
        {"channel": (m.get("channel") or {}).get("name"), "user": m.get("user"),
         "text": m.get("text"), "permalink": m.get("permalink")}
        for m in matches
    ]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Slack Web API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("channels", help="list channels")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(func=cmd_channels)

    p = sub.add_parser("history", help="recent messages in a channel")
    p.add_argument("--channel", required=True, help="channel ID, e.g. C0123456789")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("post", help="post a message")
    p.add_argument("--channel", required=True)
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_post)

    p = sub.add_parser("users", help="list workspace users")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(func=cmd_users)

    p = sub.add_parser("search", help="search messages (needs search:read on the token)")
    p.add_argument("--query", required=True)
    p.add_argument("--count", type=int, default=20)
    p.set_defaults(func=cmd_search)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
