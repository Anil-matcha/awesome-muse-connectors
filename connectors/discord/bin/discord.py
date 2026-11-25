#!/usr/bin/env python3
"""Minimal Discord API CLI for the muse-connectors discord skill.

Auth: loads the per-user `custom.discord` credential as a surrogate via the
bundled dynamic_credentials helper. Discord bot tokens are sent as
`Authorization: Bot <token>` (NOT Bearer), so the credential uses a
custom_header:Authorization placement. Muse's swap replaces the header value
only when it is exactly the surrogate, so the stored credential must be the
full `Bot <token>` string and this script sends the surrogate as the ENTIRE
header value. A composite `Bot <surrogate>` header is not swapped and 401s.
The real token never touches this script: the runtime swaps the surrogate on
approved egress, only to discord.com.

Scope: a bot sees only the servers it was invited to. It can never read the
user's own direct messages; `dm` sends a DM FROM the bot.

The read-only catch-up commands (`mentions`, `digest`) live in
discord_catchup.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.discord"
ALLOWED_HOSTS = ("discord.com",)
API = "https://discord.com/api/v10"

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


class ApiError(Exception):
    """An HTTP error from Discord. `status` is None for network failures."""

    def __init__(self, status, message: str, body: dict | None = None,
                 headers=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.body = body or {}
        self.headers = headers


def request(method: str, path: str, params: dict | None = None,
            payload: dict | None = None):
    """Make one API call; raise ApiError instead of exiting."""
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    ensure_allowed_url(url, ALLOWED_HOSTS)
    try:
        surrogate = dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    # The stored value is the full "Bot <token>" string; send the surrogate as
    # the whole header value so Muse's swap applies (see module docstring).
    req.add_header("Authorization", surrogate)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        body = {}
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        if not isinstance(body, dict):
            body = {}
        raise ApiError(exc.code, msg, body, exc.headers) from None
    except Exception as exc:  # network-level failure
        raise ApiError(None, str(exc)) from None


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None):
    try:
        return request(method, path, params=params, payload=payload)
    except ApiError as exc:
        if exc.status is None:
            sys.exit(f"error: request failed: {exc.message}")
        sys.exit(f"error: discord returned HTTP {exc.status}: {exc.message}")


def cmd_auth(_args):
    me = call("GET", "/users/@me")
    print(json.dumps({"ok": True, "username": me.get("username"),
                      "id": me.get("id")}, indent=2))


def cmd_guilds(args):
    result = call("GET", "/users/@me/guilds", params={"limit": args.limit})
    guilds = [{"id": g["id"], "name": g.get("name")} for g in result]
    print(json.dumps(guilds, indent=2))


def cmd_channels(args):
    result = call("GET", f"/guilds/{args.guild}/channels")
    channels = [{"id": c["id"], "name": c.get("name"),
                 "type": c.get("type")} for c in result]
    print(json.dumps(channels, indent=2))


def cmd_history(args):
    result = call("GET", f"/channels/{args.channel}/messages",
                  params={"limit": args.limit})
    messages = [
        {"id": m["id"],
         "author": (m.get("author") or {}).get("username"),
         "timestamp": m.get("timestamp"),
         "content": m.get("content")}
        for m in result
    ]
    print(json.dumps(messages, indent=2))


def cmd_send(args):
    result = call("POST", f"/channels/{args.channel}/messages",
                  payload={"content": args.text})
    print(json.dumps({"ok": True, "id": result.get("id")}, indent=2))


def cmd_dm(args):
    chan = call("POST", "/users/@me/channels",
                payload={"recipient_id": args.user})
    channel_id = chan.get("id")
    result = call("POST", f"/channels/{channel_id}/messages",
                  payload={"content": args.text})
    print(json.dumps({"ok": True, "channel_id": channel_id,
                      "id": result.get("id")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Discord API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the bot token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("guilds", help="list servers the bot has joined")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_guilds)

    p = sub.add_parser("channels", help="list channels in a server")
    p.add_argument("--guild", required=True, help="server (guild) ID")
    p.set_defaults(func=cmd_channels)

    p = sub.add_parser("history", help="read recent messages in a channel")
    p.add_argument("--channel", required=True, help="channel ID")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("send", help="post a message to a channel (confirm first)")
    p.add_argument("--channel", required=True, help="channel ID")
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("dm", help="send a DM from the bot to a user (confirm first); "
                                  "cannot read the user's own DMs")
    p.add_argument("--user", required=True, help="user ID")
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_dm)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import discord_catchup
    discord_catchup.register(sub, sys.modules[__name__])

    args = parser.parse_args()
    if getattr(args, "limit", None) is not None and args.limit > 100:
        sys.exit("error: --limit must be 100 or less")
    args.func(args)


if __name__ == "__main__":
    main()
