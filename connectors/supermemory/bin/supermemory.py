#!/usr/bin/env python3
"""Minimal Supermemory API CLI for the muse-connectors supermemory skill.

Auth: loads the per-user `custom.supermemory` credential as a surrogate via
the bundled dynamic_credentials helper (Bearer placement, like beehiiv). The
real API key never touches this script: the runtime swaps the surrogate on
approved egress, only to api.supermemory.ai.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.supermemory"
ALLOWED_HOSTS = ("api.supermemory.ai",)
API = "https://api.supermemory.ai"

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


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("error", body.get("detail", str(exc))))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: supermemory returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def call_multipart(path: str, file_path: str, container_tag: str | None) -> dict:
    """POST a multipart/form-data file upload (stdlib only)."""
    if not os.path.isfile(file_path):
        sys.exit(f"error: file not found: {file_path}")
    boundary = "----museconnectors" + os.urandom(8).hex()
    filename = os.path.basename(file_path)
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    parts = []
    with open(file_path, "rb") as fh:
        file_bytes = fh.read()
    parts.append(
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f'Content-Type: {ctype}\r\n\r\n'.encode("utf-8") + file_bytes + b"\r\n"
    )
    if container_tag:
        parts.append(
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="containerTag"\r\n\r\n'
            f'{container_tag}\r\n'.encode("utf-8")
        )
    body = b"".join(parts) + f"--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        API + path, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("error", body.get("detail", str(exc))))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: supermemory returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def _docs(result: dict) -> list:
    docs = result.get("documents", result.get("results", []))
    return docs if isinstance(docs, list) else []


def cmd_auth(_args):
    result = call("POST", "/v3/documents/list", payload={"limit": 1})
    docs = _docs(result)
    print(json.dumps({"ok": True, "total": result.get("total"), "sample": len(docs)}, indent=2))


def cmd_add(args):
    payload = {"content": args.content}
    if args.container_tag:
        payload["containerTag"] = args.container_tag
    if args.custom_id:
        payload["customId"] = args.custom_id
    if args.metadata:
        try:
            payload["metadata"] = json.loads(args.metadata)
        except json.JSONDecodeError:
            sys.exit("error: --metadata must be valid JSON")
    if args.task_type:
        payload["taskType"] = args.task_type
    result = call("POST", "/v3/documents", payload=payload)
    print(json.dumps({"ok": True, "id": result.get("id"), "status": result.get("status")}, indent=2))


def cmd_search(args):
    payload = {"q": args.query}
    if args.container_tag:
        payload["containerTag"] = args.container_tag
    if args.search_mode:
        payload["searchMode"] = args.search_mode
    if args.limit:
        payload["limit"] = args.limit
    result = call("POST", "/v3/documents/search", payload=payload)
    docs = _docs(result)
    out = [
        {"id": d.get("id"), "content": (d.get("content") or d.get("memory") or "")[:500],
         "score": d.get("score"), "containerTag": d.get("containerTag")}
        for d in docs
    ]
    print(json.dumps(out, indent=2))


def cmd_list(args):
    payload = {}
    if args.container_tag:
        payload["containerTag"] = args.container_tag
    payload["limit"] = args.limit
    result = call("POST", "/v3/documents/list", payload=payload)
    docs = _docs(result)
    out = [
        {"id": d.get("id"), "content": (d.get("content") or "")[:300],
         "containerTag": d.get("containerTag"), "createdAt": d.get("createdAt")}
        for d in docs
    ]
    print(json.dumps(out, indent=2))


def cmd_upload(args):
    result = call_multipart("/v3/documents/upload-file", args.file, args.container_tag)
    print(json.dumps({"ok": True, "id": result.get("id"), "status": result.get("status")}, indent=2))


def cmd_settings(args):
    try:
        payload = json.loads(args.json)
    except json.JSONDecodeError:
        sys.exit("error: --json must be valid JSON")
    result = call("PATCH", "/v3/settings", payload=payload)
    print(json.dumps({"ok": True, "result": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Supermemory API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("add", help="store a memory/document (confirm first)")
    p.add_argument("--content", required=True, help="text content to store")
    p.add_argument("--container-tag", default=None, help="per-user/project isolation (max 100 chars)")
    p.add_argument("--custom-id", default=None)
    p.add_argument("--metadata", default=None, help="JSON object")
    p.add_argument("--task-type", default=None)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("search", help="hybrid search across memories and documents")
    p.add_argument("--query", required=True)
    p.add_argument("--container-tag", default=None)
    p.add_argument("--search-mode", default=None, help="e.g. memories, documents")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("list", help="list/filter stored documents")
    p.add_argument("--container-tag", default=None)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("upload", help="upload a file (PDF, image, video, code; confirm first)")
    p.add_argument("--file", required=True, help="local file path")
    p.add_argument("--container-tag", default=None)
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("settings", help="tune memory extraction/chunking (confirm first)")
    p.add_argument("--json", required=True, help="settings payload as JSON")
    p.set_defaults(func=cmd_settings)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
