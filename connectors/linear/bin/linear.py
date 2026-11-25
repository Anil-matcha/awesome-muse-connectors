#!/usr/bin/env python3
"""Minimal Linear GraphQL CLI for the muse-connectors Linear skill.

Auth: loads the per-user `custom.linear` credential as a surrogate via the
bundled dynamic_credentials helper. The real key never touches this script:
the runtime swaps the surrogate on approved egress, only to api.linear.app.
Placement (raw Authorization header value) is resolved by the helper from the
stored connector record.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.linear"
ALLOWED_HOSTS = ("api.linear.app",)
API = "https://api.linear.app/graphql"

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


def graphql(query: str, variables: dict | None = None) -> dict:
    data = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        API, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: linear returned HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:300]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if result.get("errors"):
        sys.exit(f"error: linear graphql errors: {json.dumps(result['errors'])[:500]}")
    return result.get("data", {})


def cmd_auth(_args):
    data = graphql("{ viewer { id name email } }")
    viewer = data.get("viewer", {})
    print(json.dumps({"id": viewer.get("id"), "name": viewer.get("name"),
                      "email": viewer.get("email")}, indent=2))


def cmd_issues(_args):
    data = graphql(
        """{ viewer {
               assignedIssues(first: 20) {
                 nodes { id title
                         state { name }
                         team { key name } } } } }"""
    )
    nodes = ((data.get("viewer") or {}).get("assignedIssues") or {}).get("nodes", [])
    issues = [
        {"id": n.get("id"), "title": n.get("title"),
         "state": (n.get("state") or {}).get("name"),
         "team": (n.get("team") or {}).get("key")}
        for n in nodes
    ]
    print(json.dumps(issues, indent=2))


def cmd_create(args):
    data = graphql(
        """mutation($input: IssueCreateInput!) {
             issueCreate(input: $input) {
               success
               issue { id title } } }""",
        {"input": {"teamId": args.team_id, "title": args.title,
                   "description": args.description or ""}},
    )
    payload = data.get("issueCreate", {})
    print(json.dumps({"success": payload.get("success"),
                      "id": (payload.get("issue") or {}).get("id"),
                      "title": (payload.get("issue") or {}).get("title")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Linear GraphQL CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("issues", help="list your assigned issues")
    p.set_defaults(func=cmd_issues)

    p = sub.add_parser("create", help="create an issue")
    p.add_argument("--team-id", required=True, help="team UUID")
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.set_defaults(func=cmd_create)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
