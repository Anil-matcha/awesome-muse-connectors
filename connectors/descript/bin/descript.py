#!/usr/bin/env python3
"""Minimal Descript API CLI for the muse-connectors descript skill.

Auth: loads the per-user `custom.descript` credential as a surrogate via
the bundled dynamic_credentials helper. Descript requires a lowercase
`authorization` header (`authorization: Bearer <key>`); a capitalized
`Authorization` returns 401, so this script sets the header name verbatim
with add_unredirected_header (urllib's add_header would capitalize it).
The key value contains a colon and is used whole, never split. The real
key never touches this script: the runtime swaps the surrogate on approved
egress, only to api.descript.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.descript"
ALLOWED_HOSTS = ("api.descript.com",)
API = "https://api.descript.com"

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


def get_surrogate() -> str:
    try:
        entry = dynamic_credential_entry(CREDENTIAL_NAME)
    except DynamicCredentialError:
        sys.exit(
            f"not connected: no `{CREDENTIAL_NAME}` credential is stored.\n"
            "Connect it with the secure credential flow (see this skill's "
            "Auth section for where to find your Descript API key), then retry."
        )
    return str(entry["surrogate"]).strip()


def call(method: str, path: str, payload: dict | None = None) -> dict:
    url = API + path
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    # Verbatim lowercase header name: capitalized `Authorization` 401s.
    # The key contains a colon; it is used whole, never split.
    req.add_unredirected_header("authorization", f"Bearer {get_surrogate()}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            err = body.get("error") or body.get("message") or body
            msg = json.dumps(err) if isinstance(err, (dict, list)) else str(err)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: descript returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def summarize_project(p: dict) -> dict:
    return {"id": p.get("id"), "name": p.get("name"),
            "created_at": p.get("created_at"), "updated_at": p.get("updated_at")}


def summarize_job(j: dict) -> dict:
    return {
        "id": j.get("id"),
        "type": j.get("type") or j.get("job_type"),
        "job_state": j.get("job_state"),
        "status": j.get("status"),
        "project_id": j.get("project_id"),
        "result": j.get("result"),
        "error": j.get("error"),
    }


def cmd_auth(_args):
    result = call("GET", "/projects")
    projects = result.get("projects", result.get("data", []))
    print(json.dumps({"ok": True, "projects": len(projects)}, indent=2))


def cmd_projects(_args):
    result = call("GET", "/projects")
    projects = result.get("projects", result.get("data", []))
    print(json.dumps([summarize_project(p) for p in projects], indent=2))


def cmd_project(args):
    result = call("GET", f"/projects/{args.id}")
    proj = result.get("project", result)
    print(json.dumps(summarize_project(proj), indent=2))


def cmd_jobs(_args):
    result = call("GET", "/jobs")
    jobs = result.get("jobs", result.get("data", []))
    print(json.dumps([summarize_job(j) for j in jobs], indent=2))


def cmd_job_status(args):
    deadline = time.time() + args.timeout
    while True:
        result = call("GET", f"/jobs/{args.id}")
        job = result.get("job", result)
        state = (job.get("job_state") or "").lower()
        if not args.wait or state == "stopped" or time.time() >= deadline:
            print(json.dumps(summarize_job(job), indent=2))
            if state == "stopped":
                return
            if time.time() >= deadline:
                sys.exit(f"error: timed out after {args.timeout}s waiting for job {args.id} to stop")
            return
        time.sleep(args.interval)


def cmd_publish(args):
    payload = {}
    if args.body:
        try:
            payload = json.loads(args.body)
        except json.JSONDecodeError as exc:
            sys.exit(f"error: --body is not valid JSON: {exc}")
    if args.project_id:
        payload.setdefault("project_id", args.project_id)
    result = call("POST", "/jobs/publish", payload)
    job = result.get("job", result)
    print(json.dumps({"ok": True, "job": summarize_job(job)}, indent=2))


def cmd_job_delete(args):
    call("DELETE", f"/jobs/{args.id}")
    print(json.dumps({"ok": True, "deleted": args.id}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Descript API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key (lists projects)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("projects", help="list projects")
    p.set_defaults(func=cmd_projects)

    p = sub.add_parser("project", help="get one project")
    p.add_argument("--id", required=True, help="project id")
    p.set_defaults(func=cmd_project)

    p = sub.add_parser("jobs", help="list Underlord/agent jobs")
    p.set_defaults(func=cmd_jobs)

    p = sub.add_parser("job-status", help="get job status; --wait polls until job_state is stopped")
    p.add_argument("--id", required=True, help="job id")
    p.add_argument("--wait", action="store_true",
                   help="poll until job_state is 'stopped'")
    p.add_argument("--interval", type=int, default=10, help="poll interval in seconds")
    p.add_argument("--timeout", type=int, default=600, help="max wait in seconds")
    p.set_defaults(func=cmd_job_status)

    p = sub.add_parser("publish", help="submit a publish job (confirm first: sends content live)")
    p.add_argument("--project-id", help="project to publish")
    p.add_argument("--body", help="raw JSON body per Descript API docs (default: {})")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("job-delete", help="delete a job (confirm first)")
    p.add_argument("--id", required=True, help="job id")
    p.set_defaults(func=cmd_job_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
