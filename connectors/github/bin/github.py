#!/usr/bin/env python3
"""Minimal GitHub REST API CLI for the muse-connectors GitHub skill.

Auth: loads the per-user `custom.github` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api.github.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.github"
ALLOWED_HOSTS = ("api.github.com",)
API = "https://api.github.com"

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


def call(method: str, path: str, params: dict | None = None, payload: dict | None = None) -> object:
    url = API + path
    data = None
    headers = {"Accept": "application/vnd.github+json"}
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
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: github returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    return result


def cmd_auth(_args):
    result = call("GET", "/user")
    print(json.dumps({"login": result.get("login"), "name": result.get("name")}, indent=2))


def cmd_repos(args):
    result = call("GET", "/user/repos", params={"per_page": args.limit, "sort": "updated"})
    repos = [
        {"name": r.get("full_name"), "private": r.get("private"),
         "updated_at": r.get("updated_at")}
        for r in result
    ]
    print(json.dumps(repos, indent=2))


def split_repo(repo: str) -> tuple[str, str]:
    if "/" not in repo:
        sys.exit("error: --repo must be OWNER/REPO")
    owner, name = repo.split("/", 1)
    return owner, name


def cmd_issues(args):
    owner, name = split_repo(args.repo)
    result = call("GET", f"/repos/{owner}/{name}/issues",
                  params={"state": "open", "per_page": args.limit})
    issues = [
        {"number": i.get("number"), "title": i.get("title"), "state": i.get("state")}
        for i in result if "pull_request" not in i
    ]
    print(json.dumps(issues, indent=2))


def cmd_create_issue(args):
    owner, name = split_repo(args.repo)
    payload = {"title": args.title}
    if args.body:
        payload["body"] = args.body
    result = call("POST", f"/repos/{owner}/{name}/issues", payload=payload)
    print(json.dumps({"number": result.get("number"), "title": result.get("title"),
                      "url": result.get("html_url")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="GitHub REST API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("repos", help="list your repos")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_repos)

    p = sub.add_parser("issues", help="list open issues in a repo")
    p.add_argument("--repo", required=True, help="OWNER/REPO")
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(func=cmd_issues)

    p = sub.add_parser("create-issue", help="create an issue")
    p.add_argument("--repo", required=True, help="OWNER/REPO")
    p.add_argument("--title", required=True)
    p.add_argument("--body", default="")
    p.set_defaults(func=cmd_create_issue)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
