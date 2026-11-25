#!/usr/bin/env python3
"""Minimal Asana REST API CLI for the muse-connectors Asana skill.

Auth: loads the per-user `custom.asana` credential (a personal access token)
as a surrogate via the bundled dynamic_credentials helper. The real token
never touches this script: the runtime swaps the surrogate on approved
egress, only to app.asana.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.asana"
ALLOWED_HOSTS = ("app.asana.com",)
API = "https://app.asana.com/api/1.0"

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


def call(path: str, params: dict | None = None, payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except Exception as exc:  # network-level failure (HTTP errors surface here)
        sys.exit(f"error: request failed: {exc}")
    if "errors" in result:
        sys.exit(f"error: asana returned: {json.dumps(result['errors'])}")
    return result.get("data", {})


def my_gid() -> str:
    me = call("/users/me")
    return me.get("gid", "")


def cmd_me(_args):
    me = call("/users/me")
    print(json.dumps(
        {"gid": me.get("gid"), "name": me.get("name"), "email": me.get("email")},
        indent=2))


def cmd_tasks(args):
    tasks = call(
        "/tasks",
        params={"assignee": my_gid(),
                "opt_fields": "name,due_on,projects.name,completed"},
    )
    out = [
        {"gid": t.get("gid"), "name": t.get("name"), "due_on": t.get("due_on"),
         "completed": t.get("completed"),
         "projects": [p.get("name") for p in t.get("projects", [])]}
        for t in tasks
    ]
    print(json.dumps(out, indent=2))


def cmd_create(args):
    data = {"name": args.name}
    if args.notes:
        data["notes"] = args.notes
    if args.workspace_gid:
        data["workspace"] = args.workspace_gid
    task = call("/tasks", payload={"data": data})
    print(json.dumps({"gid": task.get("gid"), "name": task.get("name"),
                      "permalink_url": task.get("permalink_url")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Asana REST API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("me", help="verify the connection")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("tasks", help="tasks assigned to me")
    p.set_defaults(func=cmd_tasks)

    p = sub.add_parser("create", help="create a task")
    p.add_argument("--name", required=True)
    p.add_argument("--notes")
    p.add_argument("--workspace-gid", help="workspace gid (required by Asana)")
    p.set_defaults(func=cmd_create)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
