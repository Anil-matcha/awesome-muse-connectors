#!/usr/bin/env python3
"""Lodestone MCP CLI for the muse-connectors skill (stdlib only)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://lodestone.studiocorsair.com/mcp?origin=muse-directory"
ALLOWED_HOST = "lodestone.studiocorsair.com"


def get_key() -> str:
    key = os.environ.get("LODESTONE_KEY", "").strip()
    if key:
        return key
    try:
        sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
        from dynamic_credentials import get_credential
        key = (get_credential("custom.lodestone") or "").strip()
        if key:
            return key
    except Exception:
        pass
    sys.exit(
        "error: no Lodestone connector key. Set LODESTONE_KEY, or on Muse collect "
        "it as custom.lodestone via credentials.request_api_access."
    )


def rpc(method: str, params: dict | None = None):
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
            "User-Agent": "lodestone-muse-connector/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:500]}")
    except Exception as exc:
        sys.exit(f"error: request failed: {exc}")
    data = [ln[6:] for ln in raw.splitlines() if ln.startswith("data: ")]
    try:
        msg = json.loads(data[-1] if data else raw)
    except Exception:
        sys.exit(f"error: unparseable response: {raw[:300]}")
    if "error" in msg:
        sys.exit(f"error: {msg['error'].get('message', msg['error'])}")
    return msg.get("result", {})


def list_tools() -> list:
    return rpc("tools/list").get("tools", [])


def is_read_only(tool: dict) -> bool:
    return (tool.get("annotations") or {}).get("readOnlyHint") is True


def cmd_auth(_args):
    tools = list_tools()
    print(json.dumps({"ok": True, "endpoint": ENDPOINT, "tools": len(tools)}))


def cmd_tools(_args):
    for t in sorted(list_tools(), key=lambda t: t["name"]):
        mode = "read" if is_read_only(t) else "WRITE"
        print(f"{mode}\t{t['name']}\t{(t.get('annotations') or {}).get('title', '')}")


def cmd_call(args):
    try:
        arguments = json.loads(args.args)
    except Exception as exc:
        sys.exit(f"error: --args is not valid JSON: {exc}")
    tool = next((t for t in list_tools() if t["name"] == args.tool), None)
    if tool is None:
        sys.exit(f"error: unknown tool '{args.tool}' (run: tools)")
    if not is_read_only(tool) and not args.confirm:
        sys.exit(
            f"refused: '{args.tool}' is not read-only (it can create, change, spend, "
            "or send). Show the user the exact arguments, get explicit approval, "
            "then re-run with --confirm."
        )
    result = rpc("tools/call", {"name": args.tool, "arguments": arguments})
    for part in result.get("content", []):
        print(part.get("text", json.dumps(part)))
    if result.get("isError"):
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="Lodestone connector")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth", help="check the key and reach the server").set_defaults(fn=cmd_auth)
    sub.add_parser("tools", help="list tools, read or WRITE").set_defaults(fn=cmd_tools)
    c = sub.add_parser("call", help="call one tool")
    c.add_argument("tool")
    c.add_argument("--args", default="{}", help="JSON arguments")
    c.add_argument("--confirm", action="store_true", help="required for non-read-only tools")
    c.set_defaults(fn=cmd_call)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
