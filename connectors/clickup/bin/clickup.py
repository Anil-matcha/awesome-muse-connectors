#!/usr/bin/env python3
"""Minimal ClickUp API v2 CLI for the muse-connectors ClickUp skill.

Auth: loads the per-user `custom.clickup` credential as a surrogate via the
bundled dynamic_credentials helper. ClickUp's personal tokens travel as the
RAW value of the `Authorization` header (no `Bearer` prefix); the helper's
stored placement for this connector is `custom_header:Authorization`. The
real token never touches this script: the runtime swaps the surrogate on
approved egress, only to api.clickup.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.clickup"
ALLOWED_HOSTS = ("api.clickup.com",)
API = "https://api.clickup.com/api/v2"

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


def call(method: str, path: str, payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            detail = json.loads(body).get("err", body)
        except Exception:
            detail = str(exc)
        sys.exit(f"error: clickup returned HTTP {exc.code}: {detail}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    return result


def cmd_teams(_args):
    result = call("GET", "/team")
    teams = [{"id": t.get("id"), "name": t.get("name")}
             for t in result.get("teams", [])]
    print(json.dumps(teams, indent=2))


def cmd_tasks(args):
    result = call("GET", f"/list/{args.list}/task")
    tasks = [
        {"id": t.get("id"), "name": t.get("name"),
         "status": (t.get("status") or {}).get("status"),
         "due_date": t.get("due_date")}
        for t in result.get("tasks", [])
    ]
    print(json.dumps(tasks, indent=2))


def cmd_create(args):
    result = call("POST", f"/list/{args.list}/task", payload={"name": args.name})
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "name": result.get("name")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="ClickUp API v2 CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("teams", help="list workspaces (ClickUp calls them teams)")
    p.set_defaults(func=cmd_teams)

    p = sub.add_parser("tasks", help="list tasks in a list")
    p.add_argument("--list", required=True, help="list id (numeric, from the ClickUp URL)")
    p.set_defaults(func=cmd_tasks)

    p = sub.add_parser("create", help="create a task in a list")
    p.add_argument("--list", required=True, help="list id (numeric, from the ClickUp URL)")
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_create)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
