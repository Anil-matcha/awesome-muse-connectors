#!/usr/bin/env python3
"""Minimal Fly.io Machines API CLI for the muse-connectors flyio skill.

Auth: loads the per-user `custom.flyio` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.machines.dev.

Uses the Machines REST API (https://api.machines.dev/v1) only. The Fly
GraphQL endpoint is documented as unstable and is intentionally not used.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.flyio"
ALLOWED_HOSTS = ("api.machines.dev",)
API = "https://api.machines.dev/v1"

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
         payload: dict | None = None) -> object:
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", body.get("message", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: fly.io returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(args):
    result = call("GET", "/apps", params={"org_slug": args.org})
    apps = result if isinstance(result, list) else []
    print(json.dumps({"ok": True, "apps": len(apps),
                      "first": apps[0].get("name") if apps else None}, indent=2))


def cmd_apps(args):
    result = call("GET", "/apps", params={"org_slug": args.org})
    apps = result if isinstance(result, list) else []
    out = [
        {"name": a.get("name"), "id": a.get("id"), "status": a.get("status")}
        for a in apps
    ]
    print(json.dumps(out, indent=2))


def cmd_machines(args):
    result = call("GET", f"/apps/{args.app}/machines")
    machines = result if isinstance(result, list) else []
    out = [
        {"id": m.get("id"), "name": m.get("name"), "state": m.get("state"),
         "region": m.get("region"),
         "image": (m.get("config") or {}).get("image")}
        for m in machines
    ]
    print(json.dumps(out, indent=2))


def cmd_volumes(args):
    result = call("GET", f"/apps/{args.app}/volumes")
    volumes = result if isinstance(result, list) else []
    out = [
        {"id": v.get("id"), "name": v.get("name"), "size_gb": v.get("size_gb"),
         "region": v.get("region"), "attached_machine": v.get("attached_machine_id")}
        for v in volumes
    ]
    print(json.dumps(out, indent=2))


def cmd_machine_create(args):
    try:
        payload = json.loads(args.config_json)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --config-json is not valid JSON: {exc}")
    result = call("POST", f"/apps/{args.app}/machines", payload=payload)
    m = result if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "id": m.get("id"), "name": m.get("name"),
                      "state": m.get("state")}, indent=2))


def cmd_machine_stop(args):
    result = call("POST", f"/apps/{args.app}/machines/{args.id}/stop")
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_machine_start(args):
    result = call("POST", f"/apps/{args.app}/machines/{args.id}/start")
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_machine_restart(args):
    result = call("POST", f"/apps/{args.app}/machines/{args.id}/restart")
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_exec(args):
    result = call("POST", f"/apps/{args.app}/machines/{args.id}/exec",
                  payload={"command": args.command.split()})
    print(json.dumps(result if isinstance(result, dict) else
                     {"result": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Fly.io Machines API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.add_argument("--org", default="personal", help="org slug (default: personal)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("apps", help="list apps in an org")
    p.add_argument("--org", default="personal", help="org slug (default: personal)")
    p.set_defaults(func=cmd_apps)

    p = sub.add_parser("machines", help="list machines in an app")
    p.add_argument("--app", required=True, help="app name")
    p.set_defaults(func=cmd_machines)

    p = sub.add_parser("volumes", help="list volumes in an app")
    p.add_argument("--app", required=True, help="app name")
    p.set_defaults(func=cmd_volumes)

    p = sub.add_parser("machine-create", help="create a machine (confirm first)")
    p.add_argument("--app", required=True, help="app name")
    p.add_argument("--config-json", required=True,
                   help="machine config as a JSON string")
    p.set_defaults(func=cmd_machine_create)

    p = sub.add_parser("machine-stop", help="stop a machine (confirm first)")
    p.add_argument("--app", required=True, help="app name")
    p.add_argument("--id", required=True, help="machine ID")
    p.set_defaults(func=cmd_machine_stop)

    p = sub.add_parser("machine-start", help="start a machine (confirm first)")
    p.add_argument("--app", required=True, help="app name")
    p.add_argument("--id", required=True, help="machine ID")
    p.set_defaults(func=cmd_machine_start)

    p = sub.add_parser("machine-restart", help="restart a machine (confirm first)")
    p.add_argument("--app", required=True, help="app name")
    p.add_argument("--id", required=True, help="machine ID")
    p.set_defaults(func=cmd_machine_restart)

    p = sub.add_parser("exec", help="run a command in a machine (confirm first)")
    p.add_argument("--app", required=True, help="app name")
    p.add_argument("--id", required=True, help="machine ID")
    p.add_argument("--command", required=True,
                   help='command to run, e.g. "df -h"')
    p.set_defaults(func=cmd_exec)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
