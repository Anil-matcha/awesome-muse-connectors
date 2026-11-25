#!/usr/bin/env python3
"""Minimal Upstash Redis REST API CLI for the muse-connectors upstash skill.

Each Upstash database has its own host (<database-id>.upstash.io) and its own
token, so every command takes a required --db-host. The allowed egress host
is built from that flag at runtime; the surrogate is only ever swapped for
that host.

Auth: loads the per-user `custom.upstash` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this
script: the runtime swaps the surrogate on approved egress, only to the
declared <database-id>.upstash.io host.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.upstash"

RUNTIME_HOSTS: tuple = ()

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


def validate_host(raw: str) -> str:
    host = raw.strip()
    if host.startswith("https://"):
        host = host[len("https://"):]
    elif host.startswith("http://"):
        sys.exit("error: --db-host must be https (scheme optional; https assumed)")
    host = host.rstrip("/").split("/")[0]
    if not host.endswith(".upstash.io") or len(host) <= len(".upstash.io"):
        sys.exit("error: --db-host must be a valid database host "
                 "like mydb.upstash.io")
    return host


def call(method: str, path: str, payload: list | None = None) -> dict:
    if not RUNTIME_HOSTS:
        sys.exit("error: database host not configured")
    url = "https://" + RUNTIME_HOSTS[0] + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME,
                                 allowed_hosts=RUNTIME_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", body.get("message", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: Upstash returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = call("GET", "/ping")
    print(json.dumps({"ok": True, "result": result.get("result")}, indent=2))


def cmd_get(args):
    key = urllib.parse.quote(args.key, safe="")
    result = call("GET", f"/get/{key}")
    print(json.dumps({"key": args.key, "value": result.get("result")},
                     indent=2))


def cmd_set(args):
    command = ["SET", args.key, args.value]
    if args.ex is not None:
        command += ["EX", str(args.ex)]
    result = call("POST", "/", payload=command)
    print(json.dumps({"key": args.key, "result": result.get("result")},
                     indent=2))


def cmd_delete(args):
    result = call("POST", "/", payload=["DEL", args.key])
    print(json.dumps({"key": args.key,
                      "deleted": result.get("result")}, indent=2))


def cmd_pipeline(args):
    try:
        commands = json.loads(args.commands_json)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --commands-json is not valid JSON: {exc}")
    if not isinstance(commands, list) or not all(
            isinstance(c, list) for c in commands):
        sys.exit("error: --commands-json must be a JSON list of command lists")
    result = call("POST", "/pipeline", payload=commands)
    print(json.dumps({"results": result.get("result")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Upstash Redis REST CLI (muse-connectors)")
    parser.add_argument("--db-host", required=True,
                        help="database host, e.g. mydb.upstash.io (https assumed)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the token (PING)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("get", help="read a key")
    p.add_argument("--key", required=True)
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("set", help="write a key (confirm first)")
    p.add_argument("--key", required=True)
    p.add_argument("--value", required=True)
    p.add_argument("--ex", type=int, default=None,
                   help="TTL in seconds")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("delete", help="delete a key (confirm first)")
    p.add_argument("--key", required=True)
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("pipeline", help="run a batch of commands (confirm first)")
    p.add_argument("--commands-json", required=True,
                   help='JSON list of command lists, e.g. \'[["GET","a"],["SET","b","1"]]\'')
    p.set_defaults(func=cmd_pipeline)

    args = parser.parse_args()
    global RUNTIME_HOSTS
    RUNTIME_HOSTS = (validate_host(args.db_host),)
    args.func(args)


if __name__ == "__main__":
    main()
