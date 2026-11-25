#!/usr/bin/env python3
"""Minimal fal.ai API CLI for the muse-connectors fal-ai skill.

Auth: loads the per-user `custom.fal-ai` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to the
fal.ai hosts, and the CLI sends it verbatim as `Authorization: Key <key>`.

Job flow: `run --model <slug> --params '{...}'` submits to the queue and
prints a request_id; poll with `status`, fetch with `result`.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.fal-ai"
ALLOWED_HOSTS = ("fal.run", "queue.fal.run", "rest.alpha.fal.ai")
QUEUE_BASE = "https://queue.fal.run"

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


def api_key() -> str:
    try:
        return str(dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]).strip()
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")


def call(method: str, url: str, payload: dict | None = None,
         params: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    req.add_header("Authorization", f"Key {api_key()}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = body.get("detail", body.get("error", body.get("message", str(exc))))
        except Exception:
            detail = str(exc)
        sys.exit(f"error: fal.ai returned HTTP {exc.code}: {detail}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def upload_file(path: str) -> dict:
    """POST a local file to fal's CDN. Multipart field name 'file' is
    per fal's upload docs (verify against live docs if this 400s)."""
    boundary = uuid.uuid4().hex
    with open(path, "rb") as fh:
        blob = fh.read()
    name = path.rsplit("/", 1)[-1]
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + blob + f"\r\n--{boundary}--\r\n".encode("utf-8")
    url = "https://fal.run/storage/upload"
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    req.add_header("Authorization", f"Key {api_key()}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: fal.ai upload returned HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:500]}")
    except Exception as exc:
        sys.exit(f"error: upload failed: {exc}")


def cmd_auth(_args):
    # Model catalog read: free, exercises the key and the exact auth header.
    result = call("GET", "https://fal.run/models")
    models = result.get("models", result) if isinstance(result, dict) else result
    count = len(models) if isinstance(models, list) else "?"
    print(json.dumps({"ok": True, "models_catalog": count}, indent=2))


def cmd_models(_args):
    result = call("GET", "https://fal.run/models")
    models = result.get("models", []) if isinstance(result, dict) else []
    out = [{"slug": m.get("slug", m.get("id")), "title": m.get("title")}
           for m in models if isinstance(m, dict)]
    print(json.dumps(out, indent=2))


def cmd_run(args):
    model = args.model.lstrip("/")
    try:
        params = json.loads(args.params) if args.params else {}
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --params is not valid JSON: {exc}")
    if not isinstance(params, dict):
        sys.exit("error: --params must be a JSON object")
    result = call("POST", f"{QUEUE_BASE}/{model}", payload={"input": params})
    print(json.dumps({
        "ok": True, "request_id": result.get("request_id"),
        "model": model,
        "status_url_hint": f"bin/fal-ai.py status --model {model} --id <request_id>",
    }, indent=2))


def cmd_status(args):
    model = args.model.lstrip("/")
    result = call("GET", f"{QUEUE_BASE}/{model}/requests/{args.id}/status")
    print(json.dumps(result, indent=2))


def cmd_result(args):
    model = args.model.lstrip("/")
    result = call("GET", f"{QUEUE_BASE}/{model}/requests/{args.id}")
    print(json.dumps(result, indent=2))
    print("note: generated file URLs expire; download promptly and do not store the URL as the artifact.",
          file=sys.stderr)


def cmd_upload(args):
    result = upload_file(args.file)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="fal.ai API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key (free catalog read)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("models", help="list model catalog")
    p.set_defaults(func=cmd_models)

    p = sub.add_parser("run", help="submit a generation job (confirm first; costs money)")
    p.add_argument("--model", required=True,
                   help="model slug, e.g. fal-ai/flux-2-pro or fal-ai/kling-video/v2.5-turbo/text-to-video")
    p.add_argument("--params", default="{}",
                   help="model input as a JSON object, e.g. '{\"prompt\": \"a lighthouse\"}'")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("status", help="poll a queued job")
    p.add_argument("--model", required=True)
    p.add_argument("--id", required=True, help="request_id from run")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("result", help="fetch a finished job's result")
    p.add_argument("--model", required=True)
    p.add_argument("--id", required=True, help="request_id from run")
    p.set_defaults(func=cmd_result)

    p = sub.add_parser("upload", help="upload a local file to fal's CDN")
    p.add_argument("--file", required=True, help="local path")
    p.set_defaults(func=cmd_upload)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
