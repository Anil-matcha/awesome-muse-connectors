#!/usr/bin/env python3
"""Minimal Langfuse API CLI for the muse-connectors langfuse skill.

Auth: loads the per-user `custom.langfuse` credential as a surrogate via the
bundled dynamic_credentials helper. The credential stores ONE combined value
"public_key:secret_key"; the CLI splits on the first colon and sends it as
HTTP Basic auth (Authorization: Basic base64(pk:sk)). The real keys never
touch this script: the runtime swaps the surrogate on approved egress, only
to the declared Langfuse host.

--host defaults to https://cloud.langfuse.com (EU); use
https://us.cloud.langfuse.com for US projects or your self-hosted URL.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.langfuse"
DEFAULT_HOST = "https://cloud.langfuse.com"

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


def make_headers(host: str) -> tuple[dict, tuple[str, ...]]:
    if not host.startswith("https://"):
        sys.exit("error: --host must start with https://")
    host = host.rstrip("/")
    hosts = (urllib.parse.urlparse(host).hostname,)
    try:
        combined = dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    if ":" not in combined:
        sys.exit("error: credential must be in 'public_key:secret_key' format")
    public_key, _, secret_key = combined.partition(":")
    basic = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    return {"Authorization": f"Basic {basic}"}, hosts, host


def call(host: str, method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    headers, hosts, base = make_headers(host)
    url = base + path
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    ensure_allowed_url(url, allowed_hosts=hosts)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
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
        sys.exit(f"error: langfuse returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(args):
    result = call(args.host, "GET", "/api/public/prompts", params={"limit": 1})
    data = result.get("data", []) if isinstance(result, dict) else []
    print(json.dumps({"ok": True, "prompts": len(data)}, indent=2))


def cmd_traces(args):
    params = {"limit": args.limit}
    if args.session_id:
        params["sessionId"] = args.session_id
    result = call(args.host, "GET", "/api/public/traces", params=params)
    data = result.get("data", []) if isinstance(result, dict) else []
    out = [
        {"id": t.get("id"), "name": t.get("name"), "sessionId": t.get("sessionId"),
         "userId": t.get("userId"), "timestamp": t.get("timestamp")}
        for t in data
    ]
    print(json.dumps(out, indent=2))


def cmd_observations(args):
    result = call(args.host, "GET", "/api/public/v2/observations",
                  params={"limit": args.limit})
    data = result.get("data", []) if isinstance(result, dict) else []
    out = [
        {"id": o.get("id"), "traceId": o.get("traceId"), "type": o.get("type"),
         "name": o.get("name"), "model": o.get("model"),
         "startTime": o.get("startTime")}
        for o in data
    ]
    print(json.dumps(out, indent=2))


def cmd_prompts(args):
    if args.name:
        result = call(args.host, "GET", f"/api/public/prompts",
                      params={"promptName": args.name})
        data = result.get("data", []) if isinstance(result, dict) else []
        prompt = data[0] if data else {}
        print(json.dumps(prompt, indent=2))
        return
    result = call(args.host, "GET", "/api/public/prompts",
                  params={"limit": args.limit})
    data = result.get("data", []) if isinstance(result, dict) else []
    out = [
        {"name": p.get("name"), "version": p.get("version"),
         "type": p.get("type"), "updatedAt": p.get("updatedAt")}
        for p in data
    ]
    print(json.dumps(out, indent=2))


def cmd_score(args):
    payload = {"traceId": args.trace_id, "name": args.name, "value": args.value}
    result = call(args.host, "POST", "/api/public/scores", payload=payload)
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_datasets(args):
    result = call(args.host, "GET", "/api/public/datasets",
                  params={"limit": args.limit})
    data = result.get("data", []) if isinstance(result, dict) else []
    out = [
        {"name": d.get("name"), "description": d.get("description"),
         "updatedAt": d.get("updatedAt")}
        for d in data
    ]
    print(json.dumps(out, indent=2))


def cmd_dataset_item(args):
    try:
        item_input = json.loads(args.input_json)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --input-json is not valid JSON: {exc}")
    payload = {"datasetName": args.dataset_name, "input": item_input}
    result = call(args.host, "POST", "/api/public/dataset-items", payload=payload)
    item = result if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "id": item.get("id")}, indent=2))


def add_host_arg(p):
    p.add_argument("--host", default=DEFAULT_HOST,
                   help="Langfuse host (default: https://cloud.langfuse.com)")


def main():
    parser = argparse.ArgumentParser(description="Langfuse API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the credential")
    add_host_arg(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("traces", help="list traces")
    add_host_arg(p)
    p.add_argument("--session-id", default=None)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_traces)

    p = sub.add_parser("observations", help="list observations")
    add_host_arg(p)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_observations)

    p = sub.add_parser("prompts", help="list prompts or show one by name")
    add_host_arg(p)
    p.add_argument("--name", default=None, help="prompt name")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_prompts)

    p = sub.add_parser("score", help="score a trace (confirm first)")
    add_host_arg(p)
    p.add_argument("--trace-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--value", required=True, type=float)
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("datasets", help="list datasets")
    add_host_arg(p)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_datasets)

    p = sub.add_parser("dataset-item", help="add a dataset item (confirm first)")
    add_host_arg(p)
    p.add_argument("--dataset-name", required=True)
    p.add_argument("--input-json", required=True,
                   help="item input as a JSON object string")
    p.set_defaults(func=cmd_dataset_item)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
