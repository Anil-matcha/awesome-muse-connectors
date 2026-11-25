#!/usr/bin/env python3
"""Minimal trigger.dev API CLI for the muse-connectors triggerdev skill.

Auth: loads the per-user `custom.triggerdev` credential as a surrogate via
the bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.trigger.dev.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.triggerdev"
ALLOWED_HOSTS = ("api.trigger.dev",)
API = "https://api.trigger.dev"

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
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("error", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: trigger.dev returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = call("GET", "/api/v1/runs", params={"limit": 1})
    runs = result.get("runs", result.get("data", []))
    print(json.dumps({"ok": True, "runs": len(runs)}, indent=2))


def cmd_runs(args):
    result = call("GET", "/api/v1/runs", params={"limit": args.limit})
    runs = result.get("runs", result.get("data", []))
    out = [
        {"id": r.get("id"), "task": r.get("taskIdentifier"),
         "status": r.get("status"), "createdAt": r.get("createdAt")}
        for r in runs
    ]
    print(json.dumps(out, indent=2))


def cmd_run(args):
    run = call("GET", f"/api/v1/runs/{args.id}")
    data = run.get("run", run)
    print(json.dumps({
        "id": data.get("id"), "task": data.get("taskIdentifier"),
        "status": data.get("status"),
        "output": data.get("output"),
        "error": data.get("error"),
    }, indent=2))


def cmd_trigger(args):
    try:
        payload_value = json.loads(args.payload_json)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --payload-json is not valid JSON: {exc}")
    payload = {"payload": payload_value}
    if args.project_ref:
        payload["projectRef"] = args.project_ref
    result = call("POST", f"/api/v1/tasks/{args.task}/trigger",
                  payload=payload)
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "status": result.get("status")}, indent=2))


def cmd_cancel(args):
    result = call("POST", f"/api/v1/runs/{args.run_id}/cancel")
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "status": result.get("status")}, indent=2))


def cmd_schedules(_args):
    result = call("GET", "/api/v1/schedules")
    schedules = result.get("schedules", result.get("data", []))
    out = [
        {"id": s.get("id"), "task": s.get("taskIdentifier"),
         "schedule": s.get("schedule"), "active": s.get("active")}
        for s in schedules
    ]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="trigger.dev API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("runs", help="list recent runs")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_runs)

    p = sub.add_parser("run", help="show one run's status and output")
    p.add_argument("--id", required=True, help="run ID")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("trigger", help="trigger a task run (confirm first)")
    p.add_argument("--task", required=True, help="task identifier, e.g. my-task")
    p.add_argument("--payload-json", default="{}", help='e.g. \'{"x":1}\'')
    p.add_argument("--project-ref", default=None,
                   help="required when authenticating with a personal access token")
    p.set_defaults(func=cmd_trigger)

    p = sub.add_parser("cancel", help="cancel a run (confirm first)")
    p.add_argument("--run-id", required=True)
    p.set_defaults(func=cmd_cancel)

    p = sub.add_parser("schedules", help="list schedules")
    p.set_defaults(func=cmd_schedules)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
