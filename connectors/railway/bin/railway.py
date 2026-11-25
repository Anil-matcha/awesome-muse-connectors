#!/usr/bin/env python3
"""Minimal Railway API CLI for the muse-connectors railway skill.

Auth: loads the per-user `custom.railway` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to
backboard.railway.com.

Railway exposes a single GraphQL endpoint; every op is POST
{"query": ..., "variables": {...}}. Project tokens (which use a
Project-Access-Token header) are out of scope; this CLI standardizes on
account/workspace Bearer tokens.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.railway"
ALLOWED_HOSTS = ("backboard.railway.com",)
API = "https://backboard.railway.com/graphql/v2"

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
    payload = {"query": query, "variables": variables or {}}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API, data=data,
        headers={"Content-Type": "application/json"}, method="POST")
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
            errs = body.get("errors", [])
            msg = "; ".join(e.get("message", "") for e in errs) or str(exc)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: railway returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = graphql("query { me { id email } }")
    me = result.get("data", {}).get("me", {}) or {}
    print(json.dumps({"ok": True, "id": me.get("id"),
                      "email": me.get("email")}, indent=2))


def cmd_projects(args):
    result = graphql(
        "query ($first: Int) { projects(first: $first) "
        "{ edges { node { id name } } } }",
        {"first": args.limit})
    edges = result.get("data", {}).get("projects", {}).get("edges", []) or []
    projects = [
        {"id": e.get("node", {}).get("id"), "name": e.get("node", {}).get("name")}
        for e in edges
    ]
    print(json.dumps(projects, indent=2))


def cmd_project(args):
    result = graphql(
        "query ($id: String!) { project(id: $id) "
        "{ id name environments { edges { node { id name } } } } }",
        {"id": args.id})
    node = result.get("data", {}).get("project") or {}
    env_edges = node.get("environments", {}).get("edges", []) or []
    print(json.dumps({
        "id": node.get("id"), "name": node.get("name"),
        "environments": [
            {"id": e.get("node", {}).get("id"),
             "name": e.get("node", {}).get("name")}
            for e in env_edges
        ]}, indent=2))


def cmd_deployments(args):
    result = graphql(
        "query ($input: DeploymentListInput!) { deployments(input: $input) "
        "{ edges { node { id status createdAt } } } }",
        {"input": {"projectId": args.project_id, "first": args.limit}})
    edges = result.get("data", {}).get("deployments", {}).get("edges", []) or []
    deployments = [
        {"id": e.get("node", {}).get("id"),
         "status": e.get("node", {}).get("status"),
         "createdAt": e.get("node", {}).get("createdAt")}
        for e in edges
    ]
    print(json.dumps(deployments, indent=2))


def cmd_set_var(args):
    result = graphql(
        "mutation ($input: VariableUpsertInput!) "
        "{ variableUpsert(input: $input) }",
        {"input": {"projectId": args.project_id,
                   "environmentId": args.env_id,
                   "name": args.name, "value": args.value}})
    data = result.get("data", {}) or {}
    print(json.dumps({"ok": True, "result": data}, indent=2))


def cmd_redeploy(args):
    result = graphql(
        "mutation ($id: String!) { deploymentRedeploy(id: $id) { id } }",
        {"id": args.deployment_id})
    node = result.get("data", {}).get("deploymentRedeploy") or {}
    print(json.dumps({"ok": True, "id": node.get("id")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Railway API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("projects", help="list projects")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_projects)

    p = sub.add_parser("project", help="inspect one project")
    p.add_argument("--id", required=True, help="project ID")
    p.set_defaults(func=cmd_project)

    p = sub.add_parser("deployments", help="list deployments for a project")
    p.add_argument("--project-id", required=True)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_deployments)

    p = sub.add_parser("set-var", help="set an env var (confirm first)")
    p.add_argument("--project-id", required=True)
    p.add_argument("--env-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--value", required=True)
    p.set_defaults(func=cmd_set_var)

    p = sub.add_parser("redeploy", help="redeploy a deployment (confirm first)")
    p.add_argument("--deployment-id", required=True)
    p.set_defaults(func=cmd_redeploy)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
