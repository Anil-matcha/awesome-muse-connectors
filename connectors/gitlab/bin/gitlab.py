#!/usr/bin/env python3
"""Minimal GitLab REST API CLI for the muse-connectors gitlab skill.

Auth: loads the per-user `custom.gitlab` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to gitlab.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.gitlab"
ALLOWED_HOSTS = ("gitlab.com",)
API = "https://gitlab.com/api/v4"

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


def call(path: str, params: dict | None = None, payload: dict | None = None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        sys.exit(f"error: gitlab API returned HTTP {exc.code}: {body}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def enc_project(project: str) -> str:
    """Accept a numeric ID or a group/project path; URL-encode for the API."""
    return urllib.parse.quote(str(project), safe="")


def cmd_me(_args):
    user = call("/user")
    print(json.dumps(
        {"id": user.get("id"), "username": user.get("username"),
         "name": user.get("name"), "email": user.get("email")},
        indent=2,
    ))


def cmd_projects(args):
    projects = call("/projects", params={
        "membership": "true", "simple": "true", "per_page": args.limit})
    out = [{"id": p.get("id"), "name": p.get("name"),
            "path": p.get("path_with_namespace")} for p in projects]
    print(json.dumps(out, indent=2))


def cmd_mrs(args):
    mrs = call(f"/projects/{enc_project(args.project)}/merge_requests",
               params={"state": "opened", "per_page": args.limit})
    out = [{"iid": m.get("iid"), "title": m.get("title"),
            "author": (m.get("author") or {}).get("name"),
            "web_url": m.get("web_url")} for m in mrs]
    print(json.dumps(out, indent=2))


def cmd_create_issue(args):
    payload = {"title": args.title}
    if args.description:
        payload["description"] = args.description
    issue = call(f"/projects/{enc_project(args.project)}/issues", payload=payload)
    print(json.dumps(
        {"iid": issue.get("iid"), "title": issue.get("title"),
         "web_url": issue.get("web_url")},
        indent=2,
    ))


def main():
    parser = argparse.ArgumentParser(description="GitLab REST API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("me", help="verify the connection")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("projects", help="your projects")
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(func=cmd_projects)

    p = sub.add_parser("mrs", help="open merge requests for a project")
    p.add_argument("--project", required=True, help="project ID or group/project path")
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(func=cmd_mrs)

    p = sub.add_parser("create-issue", help="create an issue")
    p.add_argument("--project", required=True, help="project ID or group/project path")
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.set_defaults(func=cmd_create_issue)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
