#!/usr/bin/env python3
"""Minimal n8n API CLI for the muse-connectors n8n skill.

Auth: loads the per-user `custom.n8n` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to the
instance host you declare with --host (sent in the X-N8N-API-KEY header,
not as a Bearer token).

n8n hosts are instance-specific (https://<instance>.app.n8n.cloud/api/v1
or your self-hosted host /api/v1). --host is required and must start with
http:// or https://; the allowed-hosts check is built from it at runtime.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.n8n"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        dynamic_credential_entry,
        ensure_allowed_url,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )

FORBIDDEN_PUT_FIELDS = ("pinData", "settings")


def base_and_hosts(host: str) -> tuple[str, tuple[str, ...]]:
    if not (host.startswith("http://") or host.startswith("https://")):
        sys.exit("error: --host must start with http:// or https://")
    host = host.rstrip("/")
    parsed = urllib.parse.urlparse(host)
    return host + "/api/v1", (parsed.hostname,)


def call(host: str, method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> object:
    base, hosts = base_and_hosts(host)
    url = base + path
    data = None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    ensure_allowed_url(url, allowed_hosts=hosts)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        surrogate = dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    req.add_header("X-N8N-API-KEY", surrogate)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("error", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: n8n returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def get_workflow(host: str, wf_id: str) -> dict:
    result = call(host, "GET", f"/workflows/{wf_id}")
    if not isinstance(result, dict):
        sys.exit("error: unexpected workflow response")
    return result


def cmd_auth(args):
    result = call(args.host, "GET", "/workflows", params={"limit": 1})
    data = result.get("data", []) if isinstance(result, dict) else []
    print(json.dumps({"ok": True, "workflows": len(data)}, indent=2))


def cmd_workflows(args):
    result = call(args.host, "GET", "/workflows", params={"limit": args.limit})
    data = result.get("data", []) if isinstance(result, dict) else []
    out = [
        {"id": w.get("id"), "name": w.get("name"),
         "active": w.get("active"), "updatedAt": w.get("updatedAt")}
        for w in data
    ]
    print(json.dumps(out, indent=2))


def cmd_workflow(args):
    wf = get_workflow(args.host, args.id)
    print(json.dumps({
        "id": wf.get("id"), "name": wf.get("name"), "active": wf.get("active"),
        "nodes": wf.get("nodes"), "connections": wf.get("connections"),
        "updatedAt": wf.get("updatedAt")}, indent=2))


def cmd_create(args):
    try:
        nodes = json.loads(args.nodes_json)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --nodes-json is not valid JSON: {exc}")
    result = call(args.host, "POST", "/workflows",
                  payload={"name": args.name, "nodes": nodes})
    wf = result if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "id": wf.get("id"),
                      "name": wf.get("name")}, indent=2))


def cmd_update(args):
    # GET first, strip, modify, PUT: n8n's PUT is a full replace, so start
    # from the current workflow and merge the caller's changes on top.
    current = get_workflow(args.host, args.id)
    merged = dict(current)
    for field in FORBIDDEN_PUT_FIELDS:
        merged.pop(field, None)
    try:
        changes = json.loads(args.workflow_json)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --workflow-json is not valid JSON: {exc}")
    if not isinstance(changes, dict):
        sys.exit("error: --workflow-json must be a JSON object")
    merged.update(changes)
    result = call(args.host, "PUT", f"/workflows/{args.id}", payload=merged)
    wf = result if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "id": wf.get("id"),
                      "name": wf.get("name")}, indent=2))


def cmd_executions(args):
    params = {"limit": args.limit}
    if args.workflow_id:
        params["workflowId"] = args.workflow_id
    result = call(args.host, "GET", "/executions", params=params)
    data = result.get("data", []) if isinstance(result, dict) else []
    out = [
        {"id": e.get("id"), "workflowId": e.get("workflowId"),
         "status": e.get("status"), "startedAt": e.get("startedAt"),
         "stoppedAt": e.get("stoppedAt")}
        for e in data
    ]
    print(json.dumps(out, indent=2))


def add_host_arg(p):
    p.add_argument("--host", required=True,
                   help="n8n instance base URL, e.g. https://myname.app.n8n.cloud")


def main():
    parser = argparse.ArgumentParser(description="n8n API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    add_host_arg(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("workflows", help="list workflows")
    add_host_arg(p)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_workflows)

    p = sub.add_parser("workflow", help="inspect one workflow")
    add_host_arg(p)
    p.add_argument("--id", required=True, help="workflow ID")
    p.set_defaults(func=cmd_workflow)

    p = sub.add_parser("create", help="create a workflow")
    add_host_arg(p)
    p.add_argument("--name", required=True)
    p.add_argument("--nodes-json", required=True,
                   help="workflow nodes as a JSON array string")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("update", help="update a workflow (confirm first; full replace)")
    add_host_arg(p)
    p.add_argument("--id", required=True, help="workflow ID")
    p.add_argument("--workflow-json", required=True,
                   help="changes as a JSON object, merged onto the current workflow")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("executions", help="list executions")
    add_host_arg(p)
    p.add_argument("--workflow-id", default=None)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_executions)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
