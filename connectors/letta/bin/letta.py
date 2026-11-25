#!/usr/bin/env python3
"""Minimal Letta API CLI for the muse-connectors letta skill.

Auth: loads the per-user `custom.letta` credential as a surrogate via the
bundled dynamic_credentials helper (Bearer placement, like beehiiv). The
real API key never touches this script: the runtime swaps the surrogate on
approved egress, only to api.letta.com.

Scope is deliberately narrow: the core memory primitives (agents,
core-memory blocks, archival passages, block creation, and messaging an
agent so it records memory itself). Pagination on list calls is cursor
based (`--after` / `--before`).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.letta"
ALLOWED_HOSTS = ("api.letta.com",)
API = "https://api.letta.com/v1"

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
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("error", body.get("detail", str(exc))))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: letta returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def _agents_list(result: dict) -> list:
    agents = result.get("agents", result.get("data", result))
    return agents if isinstance(agents, list) else []


def cmd_auth(_args):
    result = call("GET", "/agents", params={"limit": 1})
    print(json.dumps({"ok": True, "agents_seen": len(_agents_list(result))}, indent=2))


def cmd_agents(args):
    params = {}
    if args.limit:
        params["limit"] = args.limit
    if args.after:
        params["after"] = args.after
    if args.before:
        params["before"] = args.before
    result = call("GET", "/agents", params=params)
    agents = _agents_list(result)
    out = [
        {"id": a.get("id"), "name": a.get("name"),
         "created_at": a.get("created_at")}
        for a in agents
    ]
    print(json.dumps(out, indent=2))


def cmd_core_memory(args):
    result = call("GET", f"/agents/{args.agent}/core-memory/blocks")
    blocks = result.get("blocks", result) if isinstance(result, dict) else result
    if isinstance(blocks, list):
        out = [
            {"id": b.get("id"), "label": b.get("label"),
             "value": (b.get("value") or "")[:1000]}
            for b in blocks
        ]
        print(json.dumps(out, indent=2))
    else:
        print(json.dumps(result, indent=2))


def cmd_archival_memory(args):
    if args.text is not None:
        # Add a passage to archival memory.
        result = call("POST", f"/agents/{args.agent}/archival-memory",
                      payload={"text": args.text})
        print(json.dumps({"ok": True, "id": result.get("id") if isinstance(result, dict) else None,
                          "result": result}, indent=2))
        return
    params = {}
    if args.limit:
        params["limit"] = args.limit
    if args.after:
        params["after"] = args.after
    if args.before:
        params["before"] = args.before
    result = call("GET", f"/agents/{args.agent}/archival-memory", params=params)
    passages = result.get("passages", result.get("data", result))
    if isinstance(passages, list):
        out = [
            {"id": p.get("id"), "text": (p.get("text") or "")[:800],
             "created_at": p.get("created_at")}
            for p in passages
        ]
        print(json.dumps(out, indent=2))
    else:
        print(json.dumps(result, indent=2))


def cmd_block_create(args):
    payload = {"label": args.label, "value": args.value}
    result = call("POST", "/blocks", payload=payload)
    block = result.get("block", result) if isinstance(result, dict) else result
    bid = block.get("id") if isinstance(block, dict) else None
    print(json.dumps({"ok": True, "id": bid}, indent=2))


def cmd_message(args):
    payload = {"messages": [{"role": "user", "content": args.message}]}
    result = call("POST", f"/agents/{args.agent}/messages", payload=payload)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Letta API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("agents", help="list agents (memory lives per agent)")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--after", default=None, help="cursor for pagination")
    p.add_argument("--before", default=None, help="cursor for pagination")
    p.set_defaults(func=cmd_agents)

    p = sub.add_parser("core-memory", help="read an agent's core-memory blocks")
    p.add_argument("--agent", required=True, help="agent ID")
    p.set_defaults(func=cmd_core_memory)

    p = sub.add_parser("archival-memory", help="list passages, or add one with --text")
    p.add_argument("--agent", required=True, help="agent ID")
    p.add_argument("--text", default=None, help="add this passage (confirm first)")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--after", default=None, help="cursor for pagination")
    p.add_argument("--before", default=None, help="cursor for pagination")
    p.set_defaults(func=cmd_archival_memory)

    p = sub.add_parser("block-create", help="create a standalone memory block (confirm first)")
    p.add_argument("--label", required=True)
    p.add_argument("--value", required=True)
    p.set_defaults(func=cmd_block_create)

    p = sub.add_parser("message", help="message the agent so it records memory itself (confirm first)")
    p.add_argument("--agent", required=True, help="agent ID")
    p.add_argument("--message", required=True)
    p.set_defaults(func=cmd_message)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
