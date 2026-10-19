#!/usr/bin/env python3
"""Taasky MCP CLI for the muse-connectors Taasky skill (stdlib only).

Taasky is a hosted MCP server (Streamable HTTP, JSON-RPC) where agents
negotiate terms for their humans. This CLI calls its account endpoint with the
user's Taasky key, so rooms are addressed by id and no per-room secret has to
be stored. Accept, reject and withdraw are parked by the server until the
human confirms in Telegram; this CLI cannot skip that.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://mcp.taasky.ai/mcp/account"
ALLOWED_HOST = "mcp.taasky.ai"
CREDENTIAL_NAME = "custom.taasky"
HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"


def get_key() -> str:
    key = os.environ.get("TAASKY_KEY", "").strip()
    if key:
        return key
    try:
        sys.path.insert(0, HELPER_PATH)
        from dynamic_credentials import get_credential
        key = (get_credential(CREDENTIAL_NAME) or "").strip()
        if key:
            return key
    except Exception:
        pass
    sys.exit(
        "error: no Taasky key. Set TAASKY_KEY, or on Muse collect it as "
        f"{CREDENTIAL_NAME} via credentials.request_api_access. The user makes "
        "one at https://mcp.taasky.ai/account."
    )


def rpc(method: str, params: dict | None = None) -> dict:
    host = urllib.parse.urlparse(ENDPOINT).hostname
    if host != ALLOWED_HOST:
        sys.exit(f"error: refusing host {host}")
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {get_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "taasky-muse-connector/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            sys.exit("error: HTTP 401: the Taasky key was not accepted. Make a new one at https://mcp.taasky.ai/account.")
        sys.exit(f"error: HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:500]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    data = [ln[6:] for ln in raw.splitlines() if ln.startswith("data: ")]
    try:
        msg = json.loads(data[-1] if data else raw)
    except Exception:
        sys.exit(f"error: unparseable response: {raw[:300]}")
    if "error" in msg:
        err = msg["error"]
        sys.exit(f"error: {err.get('message', err) if isinstance(err, dict) else err}")
    return msg.get("result", {})


def call(tool: str, arguments: dict) -> None:
    """Call one Taasky tool and print its JSON result. Tool errors exit 1."""
    result = rpc("tools/call", {"name": tool, "arguments": arguments})
    text = "\n".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
    if result.get("isError"):
        sys.exit(f"error: {text}")
    try:
        print(json.dumps(json.loads(text), indent=2, ensure_ascii=False))
    except ValueError:
        print(text)


def json_arg(value: str | None, name: str):
    """A JSON argument, given inline or as `-` for stdin."""
    if value is None:
        return None
    if value == "-":
        value = sys.stdin.read()
    try:
        return json.loads(value)
    except ValueError as exc:
        sys.exit(f"error: --{name} is not valid JSON: {exc}")


def invite_code(value: str) -> str:
    """Accept either the code or the full invite link https://mcp.taasky.ai/i/<code>."""
    m = re.search(r"/i/([^/?#\s]+)", value)
    return m.group(1) if m else value.strip()


def put(args: dict, key: str, value) -> None:
    if value is not None:
        args[key] = value


def cmd_auth(_args):
    tools = rpc("tools/list").get("tools", [])
    print(json.dumps({"ok": True, "endpoint": ENDPOINT, "tools": len(tools)}))


def cmd_tools(_args):
    for t in rpc("tools/list").get("tools", []):
        ro = (t.get("annotations") or {}).get("readOnlyHint") is True
        print(f"{t['name']}\t{'read' if ro else 'WRITE'}\t{t.get('title', '')}")


def cmd_open(args):
    a = {"subject_schema": json_arg(args.schema, "schema")}
    put(a, "limits", json_arg(args.limits, "limits"))
    put(a, "subject", json_arg(args.subject, "subject"))
    call("negotiation_open", a)


def cmd_join(args):
    a = {"invite_code": invite_code(args.invite), "subject_schema": json_arg(args.schema, "schema")}
    put(a, "limits", json_arg(args.limits, "limits"))
    call("negotiation_join", a)


def cmd_list(args):
    call("negotiation_list", {"include_closed": True} if args.include_closed else {})


def cmd_read(args):
    call("negotiation_read", {"room": args.room})


def cmd_propose(args):
    a = {"room": args.room, "verdict": args.verdict}
    put(a, "subject", json_arg(args.subject, "subject"))
    put(a, "deadline", args.deadline)
    call("negotiation_propose", a)


def cmd_respond(args):
    a = {"room": args.room, "decision": args.decision}
    put(a, "subject_hash", args.subject_hash)
    call("negotiation_respond", a)


def cmd_cancel(args):
    call("negotiation_cancel", {"room": args.room})


def main():
    parser = argparse.ArgumentParser(description="Taasky MCP CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the key and reach the server")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("tools", help="list tools; WRITE marks anything not read-only")
    p.set_defaults(func=cmd_tools)

    p = sub.add_parser("open", help="open a room; returns invite_url (and bind_url if Telegram is not linked)")
    p.add_argument("--schema", required=True, help="subject_schema JSON, or - for stdin")
    p.add_argument("--limits", help="private limits JSON, seen only by Taasky")
    p.add_argument("--subject", help="opening offer JSON, matching --schema")
    p.set_defaults(func=cmd_open)

    p = sub.add_parser("join", help="join a room from an invite link or code")
    p.add_argument("--invite", required=True, help="https://mcp.taasky.ai/i/<code> or the code")
    p.add_argument("--schema", required=True, help="your subject_schema JSON, or - for stdin")
    p.add_argument("--limits", help="private limits JSON")
    p.set_defaults(func=cmd_join)

    p = sub.add_parser("list", help="the user's rooms that are still open")
    p.add_argument("--include-closed", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("read", help="state, turn, terms on the table and every round")
    p.add_argument("--room", required=True)
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("propose", help="offer, counter or ask for detail")
    p.add_argument("--room", required=True)
    p.add_argument("--verdict", required=True, choices=["offer", "counter", "need_more_detail"])
    p.add_argument("--subject", help="terms JSON matching your schema (offer and counter)")
    p.add_argument("--deadline", help="RFC3339; replaces the room deadline, leaving it out clears it")
    p.set_defaults(func=cmd_propose)

    p = sub.add_parser("respond", help="approve or reject; the human confirms in Telegram")
    p.add_argument("--room", required=True)
    p.add_argument("--decision", required=True, choices=["approve", "reject"])
    p.add_argument("--subject-hash", help="required for approve: subject_hash from read")
    p.set_defaults(func=cmd_respond)

    p = sub.add_parser("cancel", help="withdraw; the human confirms in Telegram")
    p.add_argument("--room", required=True)
    p.set_defaults(func=cmd_cancel)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
