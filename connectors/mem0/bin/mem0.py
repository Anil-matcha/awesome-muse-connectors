#!/usr/bin/env python3
"""Minimal mem0 API CLI for the muse-connectors mem0 skill.

Auth: loads the per-user `custom.mem0` credential as a surrogate via the
bundled dynamic_credentials helper, then sends it verbatim as
`Authorization: Token <surrogate>` (mem0 uses a nonstandard scheme, not
Bearer). The real API key never touches this script: the runtime swaps the
surrogate on approved egress, only to api.mem0.ai.

Note: v3 add and search are ASYNC. They return an event_id; poll it with
the `status` subcommand (GET /v1/event/{event_id}/).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.mem0"
ALLOWED_HOSTS = ("api.mem0.ai",)
API = "https://api.mem0.ai"

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
    req.add_header("Authorization", f"Token {surrogate}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("error", body.get("detail", str(exc))))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: mem0 returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    # Cheap read probe: a list scoped to a sentinel user. 401 means bad key.
    result = call("GET", "/v1/memories/", params={"user_id": "__auth_probe"})
    mems = result if isinstance(result, list) else result.get("results", result)
    count = len(mems) if isinstance(mems, list) else 0
    print(json.dumps({"ok": True, "probe_memories": count}, indent=2))


def cmd_add(args):
    payload = {
        "messages": [{"role": args.role, "content": args.message}],
    }
    if args.user_id:
        payload["user_id"] = args.user_id
    if args.agent_id:
        payload["agent_id"] = args.agent_id
    if args.app_id:
        payload["app_id"] = args.app_id
    if args.run_id:
        payload["run_id"] = args.run_id
    result = call("POST", "/v3/memories/add/", payload=payload)
    print(json.dumps({
        "ok": True,
        "event_id": result.get("event_id"),
        "note": "add is async; poll with: status --event-id " + str(result.get("event_id")),
    }, indent=2))


def cmd_search(args):
    payload = {"query": args.query, "filters": {"user_id": args.user_id}}
    result = call("POST", "/v3/memories/search/", payload=payload)
    print(json.dumps({
        "ok": True,
        "event_id": result.get("event_id"),
        "note": "search is async; poll with: status --event-id " + str(result.get("event_id")),
    }, indent=2))


def cmd_list(args):
    result = call("GET", "/v1/memories/", params={"user_id": args.user_id})
    mems = result if isinstance(result, list) else result.get("results", [])
    out = [
        {"id": m.get("id"), "memory": m.get("memory"),
         "created_at": m.get("created_at"), "updated_at": m.get("updated_at")}
        for m in (mems if isinstance(mems, list) else [])
    ]
    if args.limit:
        out = out[:args.limit]
    print(json.dumps(out, indent=2))


def cmd_get(args):
    result = call("GET", f"/v1/memories/{args.id}/")
    print(json.dumps(result, indent=2))


def cmd_history(args):
    result = call("GET", f"/v1/memories/{args.id}/history/")
    print(json.dumps(result, indent=2))


def cmd_delete(args):
    result = call("DELETE", f"/v1/memories/{args.id}/")
    print(json.dumps({"ok": True, "id": args.id, "result": result}, indent=2))


def cmd_wipe(args):
    # Scoped wipe: DELETE /v1/memories/ removes every memory in the scope.
    result = call("DELETE", "/v1/memories/", params={"user_id": args.user_id})
    print(json.dumps({"ok": True, "scope": args.user_id, "result": result}, indent=2))


def cmd_status(args):
    result = call("GET", f"/v1/event/{args.event_id}/")
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="mem0 API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("add", help="extract and store a memory from a message (async)")
    p.add_argument("--message", required=True, help="message text to remember")
    p.add_argument("--role", default="user", help="message role (default: user)")
    p.add_argument("--user-id", default=None)
    p.add_argument("--agent-id", default=None)
    p.add_argument("--app-id", default=None)
    p.add_argument("--run-id", default=None)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("search", help="semantic search (async, returns event_id)")
    p.add_argument("--query", required=True)
    p.add_argument("--user-id", required=True, help="scope for filters")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("list", help="list memories for a user")
    p.add_argument("--user-id", required=True)
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("get", help="get one memory")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("history", help="change log of one memory")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("delete", help="delete one memory (confirm first)")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("wipe", help="delete ALL memories in a user scope (confirm first)")
    p.add_argument("--user-id", required=True)
    p.set_defaults(func=cmd_wipe)

    p = sub.add_parser("status", help="poll an async add/search event")
    p.add_argument("--event-id", required=True)
    p.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
