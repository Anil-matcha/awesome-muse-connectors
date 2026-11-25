#!/usr/bin/env python3
"""Sentry API CLI for the muse-connectors sentry skill.

Auth: loads the per-user `custom.sentry` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to sentry.io.

HONESTY NOTE: the issue-update endpoints below are taken from Sentry's public
API docs (docs.sentry.io "Update an Issue", org-scoped
PUT /api/0/organizations/{org}/issues/{issue_id}/) and have not been verified
in a live flow. Per those docs, "archived" is NOT a documented status value:
the API's archive-equivalent is status="ignored" (optionally with an
archived_* substatus), so the `archive` command sends {"status": "ignored"}.
Issue updates need a token with the `event:write` (or `event:admin`) scope,
beyond the read scopes in SKILL.md.

resolve/assign/archive require an exact --confirm string echoed by the CLI,
on every call.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.sentry"
ALLOWED_HOSTS = ("sentry.io",)
API = "https://sentry.io/api/0"

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


def call(path: str, params: dict | None = None, method: str = "GET",
         payload: dict | None = None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        sys.exit(f"error: sentry API returned HTTP {exc.code}: {body}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_orgs(_args):
    orgs = call("/organizations/")
    out = [{"slug": o.get("slug"), "name": o.get("name")} for o in orgs]
    print(json.dumps(out, indent=2))


def cmd_projects(args):
    org = urllib.parse.quote(args.org, safe="")
    projects = call(f"/organizations/{org}/projects/")
    out = [{"slug": p.get("slug"), "name": p.get("name"), "platform": p.get("platform")}
           for p in projects]
    print(json.dumps(out, indent=2))


def cmd_issues(args):
    org = urllib.parse.quote(args.org, safe="")
    issues = call(f"/organizations/{org}/issues/", params={
        "query": args.query, "sort": "freq",
        "statsPeriod": args.period, "limit": args.limit})
    out = [{"id": i.get("id"), "title": i.get("title"),
            "level": i.get("level"), "count": i.get("count")}
           for i in issues]
    print(json.dumps(out, indent=2))


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def issue_path(args) -> tuple[str, str]:
    org = urllib.parse.quote(args.org, safe="")
    issue_id = urllib.parse.quote(args.issue_id, safe="")
    return f"/organizations/{org}/issues/{issue_id}/", args.issue_id


def print_issue(issue: dict) -> None:
    assigned = issue.get("assignedTo") or {}
    print(json.dumps(
        {"id": issue.get("id"), "shortId": issue.get("shortId"),
         "title": issue.get("title"), "status": issue.get("status"),
         "substatus": issue.get("substatus"),
         "assignedTo": (assigned.get("email") or assigned.get("name")
                        or assigned.get("id"))},
        indent=2))


def cmd_resolve(args):
    path, issue_id = issue_path(args)
    expected = f"resolve issue {issue_id}"
    need_confirm(
        args, expected,
        f"marking Sentry issue {issue_id} as resolved (it will regress "
        "back to unresolved if the error recurs).")
    issue = call(path, method="PUT", payload={"status": "resolved"})
    print_issue(issue)


def cmd_archive(args):
    path, issue_id = issue_path(args)
    expected = f"archive issue {issue_id}"
    need_confirm(
        args, expected,
        f"archiving Sentry issue {issue_id} (sent as status=\"ignored\", "
        "the API's archive-equivalent; see the HONESTY NOTE in this script).")
    issue = call(path, method="PUT", payload={"status": "ignored"})
    print_issue(issue)


def cmd_assign(args):
    path, issue_id = issue_path(args)
    expected = f"assign issue {issue_id} to {args.assignee}"
    need_confirm(
        args, expected,
        f"assigning Sentry issue {issue_id} to {args.assignee!r}.")
    issue = call(path, method="PUT", payload={"assignedTo": args.assignee})
    print_issue(issue)


def main():
    parser = argparse.ArgumentParser(description="Sentry API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("orgs", help="your organizations")
    p.set_defaults(func=cmd_orgs)

    p = sub.add_parser("projects", help="projects in an org")
    p.add_argument("--org", required=True, help="organization slug")
    p.set_defaults(func=cmd_projects)

    p = sub.add_parser("issues", help="unresolved issues, last 24h, by frequency")
    p.add_argument("--org", required=True, help="organization slug")
    p.add_argument("--query", default="is:unresolved",
                   help="Sentry search syntax (default: is:unresolved)")
    p.add_argument("--period", default="24h",
                   help="stats window, e.g. 1h, 24h, 14d")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_issues)

    p = sub.add_parser("resolve",
                       help="mark an issue resolved (needs --confirm)")
    p.add_argument("--org", required=True, help="organization slug")
    p.add_argument("--issue-id", required=True,
                   help="numeric issue id (the `id` field from `issues`)")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("archive",
                       help="archive an issue (needs --confirm)")
    p.add_argument("--org", required=True, help="organization slug")
    p.add_argument("--issue-id", required=True,
                   help="numeric issue id (the `id` field from `issues`)")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_archive)

    p = sub.add_parser("assign",
                       help="assign an issue to a user or team "
                            "(needs --confirm)")
    p.add_argument("--org", required=True, help="organization slug")
    p.add_argument("--issue-id", required=True,
                   help="numeric issue id (the `id` field from `issues`)")
    p.add_argument("--assignee", required=True,
                   help="user id, user:<id>, username, user email, or "
                        "team:<team_id>")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_assign)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
