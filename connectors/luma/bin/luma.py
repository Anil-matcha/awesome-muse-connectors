#!/usr/bin/env python3
"""Minimal Luma Dream Machine API CLI for the muse-connectors luma skill.

Auth: loads the per-user `custom.luma` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.lumalabs.ai, sent as `Authorization: Bearer <key>`.

COST WARNING: API credits are a separate product from the Luma app
subscription: separate billing, separate credit balance. Generations here
spend API credits (~$0.08/sec for Ray2-class video; recheck the live
pricing page). Poll no faster than every ~5 seconds.

UPLOAD NOTE: the upload endpoint path below is the documented image-upload
surface per the research dossier; reconcile the exact path against
docs.lumalabs.ai if it 404s before live use.
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
CREDENTIAL_NAME = "custom.luma"
ALLOWED_HOSTS = ("api.lumalabs.ai",)
BASE = "https://api.lumalabs.ai/dream-machine/v1"

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


def call(method: str, path: str, payload: dict | None = None,
         params: dict | None = None) -> dict:
    url = BASE + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    req.add_header("Authorization", f"Bearer {api_key()}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("detail", body.get("error", body.get("message", str(exc))))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: Luma returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def _parse_json_arg(extra: str | None) -> dict:
    if not extra:
        return {}
    try:
        obj = json.loads(extra)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --json is not valid JSON: {exc}")
    if not isinstance(obj, dict):
        sys.exit("error: --json must be a JSON object")
    return obj


def _summarize(g: dict) -> dict:
    return {
        "id": g.get("id"), "state": g.get("state"),
        "failure_reason": g.get("failure_reason"),
        "assets": g.get("assets"),
        "created_at": g.get("created_at"),
    }


def cmd_auth(_args):
    result = call("GET", "/generations", params={"limit": 1})
    gens = result.get("generations", []) if isinstance(result, dict) else []
    print(json.dumps({"ok": True, "recent_generations": len(gens)}, indent=2))


def cmd_generate(args):
    payload = {"prompt": args.prompt}
    if args.model:
        payload["model"] = args.model
    if args.image_url:
        payload["keyframes"] = {"frame0": {"type": "image", "url": args.image_url}}
    payload.update(_parse_json_arg(args.json))
    result = call("POST", "/generations", payload=payload)
    gen = result if isinstance(result, dict) else {}
    print(json.dumps(_summarize(gen), indent=2))
    print(f"poll with: bin/luma.py status --id {gen.get('id')} (no faster than every 5s)",
          file=sys.stderr)


def cmd_status(args):
    result = call("GET", f"/generations/{args.id}")
    gen = result if isinstance(result, dict) else {}
    print(json.dumps(_summarize(gen), indent=2))
    state = gen.get("state")
    if state == "completed":
        print("note: output URLs are temporary; download promptly.",
              file=sys.stderr)
    elif state == "failed":
        print(f"failure reason: {gen.get('failure_reason')}", file=sys.stderr)


def cmd_cancel(args):
    result = call("DELETE", f"/generations/{args.id}")
    print(json.dumps({"ok": True, "id": args.id, "result": result}, indent=2))


def cmd_upload(args):
    boundary = uuid.uuid4().hex
    with open(args.file, "rb") as fh:
        blob = fh.read()
    name = args.file.rsplit("/", 1)[-1]
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + blob + f"\r\n--{boundary}--\r\n".encode("utf-8")
    url = BASE + "/upload"  # see UPLOAD NOTE above
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    req.add_header("Authorization", f"Bearer {api_key()}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            print(json.dumps(json.loads(resp.read().decode("utf-8", errors="replace")), indent=2))
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: Luma upload returned HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:500]}")
    except Exception as exc:
        sys.exit(f"error: upload failed: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Luma Dream Machine API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key (free generations read)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("generate", help="text/image-to-video (confirm first; API-credits billed)")
    p.add_argument("--prompt", required=True)
    p.add_argument("--model", default=None,
                   help="model id; confirm the current id in docs.lumalabs.ai before use")
    p.add_argument("--image-url", default=None,
                   help="image URL for image-to-video keyframes (upload first with `upload`)")
    p.add_argument("--json", default=None,
                   help="extra fields (aspect_ratio, duration, etc.) as a JSON object")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("status", help="poll a generation (no faster than every 5s)")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("cancel", help="cancel a queued/running generation")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_cancel)

    p = sub.add_parser("upload", help="upload an image for reference frames")
    p.add_argument("--file", required=True, help="local path")
    p.set_defaults(func=cmd_upload)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
