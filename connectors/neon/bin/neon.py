#!/usr/bin/env python3
"""Neon serverless Postgres API CLI for the muse-connectors neon skill.

Auth: loads the per-user `custom.neon` credential as a surrogate via the
bundled dynamic_credentials helper. Neon uses an API key sent as
Authorization: Bearer. The real key never touches this script: the runtime
swaps the surrogate on approved egress, only to console.neon.tech.

Safety: plain reads are GETs. Creating or deleting a branch provisions or
destroys a live database branch with compute, so both are HIGH actuations
and require an exact --confirm string echoed by the CLI on every call.
Connection URIs contain database passwords: this CLI masks the password
portion whenever it displays them and never prints a full credential.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.neon"
ALLOWED_HOSTS = ("console.neon.tech",)
BASE = "https://console.neon.tech/api/v2"
CONNECT_GUIDANCE = (
    "not connected: create a Neon API key (Neon console > Account settings "
    "> API keys) and collect it via the secure credential flow "
    "(credentials.request_api_access) as `custom.neon`, then retry."
)

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


def call(method: str, path: str, payload: dict | None = None) -> dict:
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        if "missing" in str(exc) or "surrogate" in str(exc):
            sys.exit(CONNECT_GUIDANCE)
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 204:
                return {}
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            msg = body[:500]
        except Exception:
            msg = str(exc)
        sys.exit(f"error: neon returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def mask_uri(uri):
    """Hide the password portion of a Postgres connection URI."""
    if not isinstance(uri, str):
        return uri
    return re.sub(r"(://[^:/@\s]+:)[^@\s]+(@)", r"\1***\2", uri)


def mask_uris(uris):
    return [mask_uri(u) for u in (uris or [])]


def cmd_auth(args):
    result = call("GET", "/projects")
    projs = result.get("projects", [])
    print(json.dumps({"ok": True, "project_count": len(projs),
                      "projects": [p.get("name") for p in projs]},
                     indent=2))


def cmd_projects(args):
    result = call("GET", "/projects")
    projs = [{"id": p.get("id"), "name": p.get("name"),
              "region_id": p.get("region_id"),
              "pg_version": p.get("pg_version"),
              "created_at": p.get("created_at")}
             for p in result.get("projects", [])]
    print(json.dumps(projs, indent=2))


def cmd_project_get(args):
    result = call("GET", f"/projects/{args.project_id}")
    p = result.get("project", {})
    print(json.dumps({"id": p.get("id"), "name": p.get("name"),
                      "region_id": p.get("region_id"),
                      "pg_version": p.get("pg_version"),
                      "created_at": p.get("created_at"),
                      "store_passwords": p.get("store_passwords")},
                     indent=2))


def cmd_branches(args):
    result = call("GET", f"/projects/{args.project_id}/branches")
    branches = [{"id": b.get("id"), "name": b.get("name"),
                 "created_at": b.get("created_at")}
                for b in result.get("branches", [])]
    print(json.dumps(branches, indent=2))


def cmd_branch_create(args):
    expected = f"create branch {args.name} in project {args.project_id}"
    need_confirm(
        args, expected,
        "creating a Neon branch provisions a live database branch with "
        "compute; it can incur billable usage.")
    payload = {"branch": {"name": args.name}}
    if args.parent_branch_id:
        payload["branch"]["parent_id"] = args.parent_branch_id
    result = call("POST", f"/projects/{args.project_id}/branches", payload)
    b = result.get("branch", {})
    print(json.dumps({"ok": True, "branch_id": b.get("id"),
                      "name": b.get("name"),
                      "connection_uris_masked": mask_uris(
                          result.get("connection_uris")),
                      "warning": "passwords masked; never paste connection "
                                 "strings into chat"}, indent=2))


def cmd_branch_delete(args):
    expected = (f"delete branch {args.branch_id} in project "
                f"{args.project_id}")
    need_confirm(
        args, expected,
        "deleting a Neon branch is IRREVERSIBLE: the branch, its compute "
        "endpoint and its data are destroyed.")
    call("DELETE",
         f"/projects/{args.project_id}/branches/{args.branch_id}")
    print(json.dumps({"ok": True, "branch_id": args.branch_id,
                      "note": "branch deleted"}, indent=2))


def cmd_databases(args):
    result = call("GET", f"/projects/{args.project_id}/databases")
    dbs = [{"id": d.get("id"), "name": d.get("name"),
            "owner_name": d.get("owner_name"),
            "branch_id": d.get("branch_id"),
            "created_at": d.get("created_at")}
           for d in result.get("databases", [])]
    print(json.dumps(dbs, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Neon serverless Postgres API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("projects", help="list projects")
    p.set_defaults(func=cmd_projects)

    p = sub.add_parser("project-get", help="retrieve one project")
    p.add_argument("--project-id", required=True)
    p.set_defaults(func=cmd_project_get)

    p = sub.add_parser("branches", help="list branches in a project")
    p.add_argument("--project-id", required=True)
    p.set_defaults(func=cmd_branches)

    p = sub.add_parser("branch-create",
                       help="create a branch (HIGH, provisions billable "
                            "compute)")
    p.add_argument("--project-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--parent-branch-id", default=None,
                   help="branch id to branch from (default: main)")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_branch_create)

    p = sub.add_parser("branch-delete",
                       help="delete a branch (HIGH, irreversible)")
    p.add_argument("--project-id", required=True)
    p.add_argument("--branch-id", required=True)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_branch_delete)

    p = sub.add_parser("databases", help="list databases in a project")
    p.add_argument("--project-id", required=True)
    p.set_defaults(func=cmd_databases)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
