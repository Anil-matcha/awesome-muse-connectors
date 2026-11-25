#!/usr/bin/env python3
"""Minimal Vercel REST API CLI for the muse-connectors vercel skill.

Auth: loads the per-user `custom.vercel` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api.vercel.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.vercel"
ALLOWED_HOSTS = ("api.vercel.com",)
API = "https://api.vercel.com"

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
        sys.exit(f"error: vercel API returned HTTP {exc.code}: {body}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_me(_args):
    user = call("/v2/user").get("user", {})
    print(json.dumps(
        {"id": user.get("id"), "username": user.get("username"),
         "email": user.get("email"), "name": user.get("name")},
        indent=2,
    ))


def cmd_projects(args):
    result = call("/v9/projects", params={"limit": args.limit})
    projects = [
        {"id": p.get("id"), "name": p.get("name"), "framework": p.get("framework")}
        for p in result.get("projects", [])
    ]
    print(json.dumps(projects, indent=2))


def cmd_deployments(args):
    result = call(
        "/v6/deployments",
        params={"projectId": args.project, "limit": args.limit},
    )
    deploys = [
        {"url": d.get("url"), "state": d.get("state"), "createdAt": d.get("createdAt")}
        for d in result.get("deployments", [])
    ]
    print(json.dumps(deploys, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Vercel REST API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("me", help="verify the connection (your user)")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("projects", help="list projects")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_projects)

    p = sub.add_parser("deployments", help="recent deployments for a project")
    p.add_argument("--project", required=True, help="project name or ID")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_deployments)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
