#!/usr/bin/env python3
"""Minimal Todoist REST API v1 CLI for the muse-connectors Todoist skill.

Auth: loads the per-user `custom.todoist` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api.todoist.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.todoist"
ALLOWED_HOSTS = ("api.todoist.com",)
API = "https://api.todoist.com/api/v1"

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


def call(method: str, path: str, payload: dict | None = None, params: dict | None = None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
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
            if resp.status == 204:
                return None
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            detail = json.loads(body).get("error", body)
        except Exception:
            detail = str(exc)
        sys.exit(f"error: todoist returned HTTP {exc.code}: {detail}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_tasks(args):
    result = call("GET", "/tasks", params={"limit": args.limit})
    tasks = [
        {"id": t.get("id"), "content": t.get("content"),
         "due": (t.get("due") or {}).get("date"),
         "priority": t.get("priority"), "project_id": t.get("project_id")}
        for t in result.get("results", [])
    ]
    print(json.dumps(tasks, indent=2))


def cmd_create(args):
    payload = {"content": args.content}
    if args.project_id:
        payload["project_id"] = args.project_id
    result = call("POST", "/tasks", payload=payload)
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "content": result.get("content")}, indent=2))


def cmd_complete(args):
    call("POST", f"/tasks/{args.id}/close")
    print(json.dumps({"ok": True, "id": args.id, "completed": True}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Todoist REST API v1 CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("tasks", help="list tasks")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_tasks)

    p = sub.add_parser("create", help="create a task")
    p.add_argument("--content", required=True)
    p.add_argument("--project-id", help="project id (optional)")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("complete", help="mark a task done")
    p.add_argument("--id", required=True, help="task id from `tasks` output")
    p.set_defaults(func=cmd_complete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
