#!/usr/bin/env python3
"""Minimal TickTick Open API CLI for the muse-connectors ticktick skill.

Auth: loads the per-user `custom.ticktick` credential as a surrogate via the
bundled dynamic_credentials helper. The real OAuth token never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.ticktick.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.ticktick"
ALLOWED_HOSTS = ("api.ticktick.com",)
API = "https://api.ticktick.com/open/v1"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        add_surrogate_to_request,
        read_response_body,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None):
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
            raw = read_response_body(resp).decode("utf-8", errors="replace").strip()
            # complete/delete return an empty body on success
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("error", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: ticktick returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = call("GET", "/project")
    print(json.dumps({"ok": True, "projects": len(result)}, indent=2))


def cmd_projects(args):
    result = call("GET", "/project")
    if not isinstance(result, list):
        sys.exit("error: unexpected projects response")
    projects = [
        {"id": p["id"], "name": p.get("name"), "kind": p.get("kind")}
        for p in result
    ]
    print(json.dumps(projects, indent=2))


def cmd_project_data(args):
    result = call("GET", f"/project/{args.project_id}/data")
    project = result.get("project", {})
    tasks = [
        {"id": t["id"], "title": t.get("title"), "status": t.get("status"),
         "dueDate": t.get("dueDate"), "priority": t.get("priority")}
        for t in result.get("tasks", [])
    ]
    print(json.dumps({"project": {"id": project.get("id"),
                                  "name": project.get("name")},
                      "tasks": tasks}, indent=2))


def cmd_task_create(args):
    payload: dict = {"title": args.title}
    if args.project_id:
        payload["projectId"] = args.project_id
    if args.content:
        payload["content"] = args.content
    if args.due_date:
        payload["dueDate"] = args.due_date
    if args.priority is not None:
        payload["priority"] = args.priority
    result = call("POST", "/task", payload=payload)
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "title": result.get("title")}, indent=2))


def cmd_task_complete(args):
    call("POST", f"/project/{args.project_id}/task/{args.task_id}/complete")
    print(json.dumps({"ok": True, "completed": args.task_id}, indent=2))


def cmd_task_delete(args):
    call("DELETE", f"/project/{args.project_id}/task/{args.task_id}")
    print(json.dumps({"ok": True, "deleted": args.task_id}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="TickTick Open API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the OAuth token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("projects", help="list task lists (projects)")
    p.set_defaults(func=cmd_projects)

    p = sub.add_parser("project-data", help="list a project's tasks and columns")
    p.add_argument("--project-id", required=True)
    p.set_defaults(func=cmd_project_data)

    p = sub.add_parser("task-create", help="create a task (confirm first)")
    p.add_argument("--title", required=True)
    p.add_argument("--project-id", default=None)
    p.add_argument("--content", default=None, help="notes for the task")
    p.add_argument("--due-date", default=None,
                   help="e.g. 2026-09-17T09:00:00+0000")
    p.add_argument("--priority", type=int, default=None,
                   help="0 (none) to 5 (highest)")
    p.set_defaults(func=cmd_task_create)

    p = sub.add_parser("task-complete", help="complete a task")
    p.add_argument("--project-id", required=True)
    p.add_argument("--task-id", required=True)
    p.set_defaults(func=cmd_task_complete)

    p = sub.add_parser("task-delete", help="delete a task (confirm first)")
    p.add_argument("--project-id", required=True)
    p.add_argument("--task-id", required=True)
    p.set_defaults(func=cmd_task_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
