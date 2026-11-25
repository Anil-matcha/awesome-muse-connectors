#!/usr/bin/env python3
"""Minimal Kling AI API CLI for the muse-connectors kling skill.

Auth (unusual): the per-user `custom.kling` credential stores
`access_key:secret_key` as ONE value (the langfuse two-secret precedent).
The CLI splits on the FIRST colon, mints a short-lived HS256 JWT per request
(stdlib hmac; iss = access key, exp ~30 min), and sends
`Authorization: Bearer <jwt>`. The secret never leaves the vault path: the
runtime only swaps the surrogate for api.klingai.com egress.

Job flow: `text2video`/`image2video` submit and print a task_id; poll with
`status` until done. Generated asset URLs are short-lived: download promptly.
Prepaid resource packs; failed tasks reportedly not charged. fal.ai hosts
Kling too, with simpler auth (trade-off: fal markup).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.kling"
ALLOWED_HOSTS = ("api.klingai.com",)
BASE = "https://api.klingai.com"

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


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def mint_jwt() -> str:
    try:
        combined = str(dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]).strip()
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    if ":" not in combined:
        sys.exit("error: credential must be in 'access_key:secret_key' format")
    access_key, _, secret_key = combined.partition(":")
    if not access_key or not secret_key:
        sys.exit("error: credential must be in 'access_key:secret_key' format")
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "iss": access_key, "nbf": now, "exp": now + 1800,
    }).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = _b64url(hmac.new(secret_key.encode("utf-8"), signing_input,
                            hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


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
    req.add_header("Authorization", f"Bearer {mint_jwt()}")
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
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: Kling returned HTTP {exc.code}: {msg}")
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


def _summarize_task(result: dict) -> dict:
    data = result.get("data", {}) if isinstance(result, dict) else {}
    videos = data.get("videos", []) if isinstance(data, dict) else []
    return {
        "task_id": data.get("task_id"),
        "task_status": data.get("task_status"),
        "task_status_msg": data.get("task_status_msg"),
        "videos": [{"url": v.get("url"), "duration": v.get("duration")}
                   for v in videos if isinstance(v, dict)],
    }


def cmd_auth(_args):
    # No documented zero-cost probe; mint a fresh JWT and hit a task-status
    # lookup for a placeholder id. 404 means auth passed (bad id, good key);
    # 401 means the key pair is wrong. A fresh JWT is free.
    jwt = mint_jwt()
    url = BASE + "/v1/videos/auth-probe-placeholder"
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {jwt}")
    try:
        urllib.request.urlopen(req, timeout=30)
        print(json.dumps({"ok": True, "note": "unexpected 200 from probe"}, indent=2))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print(json.dumps({"ok": True, "note": "JWT minted and accepted (probe id 404 as expected)"}, indent=2))
        elif exc.code == 401:
            sys.exit("error: auth failed (401): access key / secret key pair rejected")
        else:
            sys.exit(f"error: auth probe returned HTTP {exc.code}")
    except Exception as exc:
        sys.exit(f"error: auth probe failed: {exc}")


def cmd_text2video(args):
    payload = {"prompt": args.prompt}
    if args.model:
        payload["model_name"] = args.model
    payload.update(_parse_json_arg(args.json))
    result = call("POST", "/v1/videos/text2video", payload=payload)
    data = result.get("data", {}) if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "task_id": data.get("task_id")}, indent=2))
    print(f"poll with: bin/kling.py status --task-id {data.get('task_id')}", file=sys.stderr)


def cmd_image2video(args):
    payload = {"image_url": args.image_url}
    if args.prompt:
        payload["prompt"] = args.prompt
    if args.model:
        payload["model_name"] = args.model
    payload.update(_parse_json_arg(args.json))
    result = call("POST", "/v1/videos/image2video", payload=payload)
    data = result.get("data", {}) if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "task_id": data.get("task_id")}, indent=2))
    print(f"poll with: bin/kling.py status --task-id {data.get('task_id')}", file=sys.stderr)


def cmd_status(args):
    result = call("GET", f"/v1/videos/{args.task_id}")
    out = _summarize_task(result)
    print(json.dumps(out, indent=2))
    if out["task_status"] == "succeed":
        print("note: asset URLs are short-lived; download immediately and do not store the URL as the artifact.",
              file=sys.stderr)
    elif out["task_status"] == "failed":
        print(f"failure: {out['task_status_msg']}", file=sys.stderr)


def cmd_extend(args):
    payload = {"task_id": args.task_id}
    payload.update(_parse_json_arg(args.json))
    result = call("POST", "/v1/videos/extend", payload=payload)
    data = result.get("data", {}) if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "task_id": data.get("task_id")}, indent=2))


def cmd_lip_sync(args):
    payload = _parse_json_arg(args.json)
    if not payload:
        sys.exit("error: --json with the lip-sync spec is required "
                 "(voice_id/audio_url, input video, etc. per Kling docs)")
    result = call("POST", "/v1/videos/lip-sync", payload=payload)
    data = result.get("data", {}) if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "task_id": data.get("task_id")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Kling AI API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="mint a JWT and verify it is accepted (free)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("text2video", help="text-to-video (confirm first; billed)")
    p.add_argument("--prompt", required=True)
    p.add_argument("--model", default=None, help="e.g. kling-v2.6; confirm current model ids in Kling docs")
    p.add_argument("--json", default=None, help="extra fields (duration, aspect_ratio, etc.) as a JSON object")
    p.set_defaults(func=cmd_text2video)

    p = sub.add_parser("image2video", help="image-to-video (confirm first; billed)")
    p.add_argument("--image-url", required=True)
    p.add_argument("--prompt", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--json", default=None, help="extra fields as a JSON object")
    p.set_defaults(func=cmd_image2video)

    p = sub.add_parser("status", help="poll a video task")
    p.add_argument("--task-id", required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("extend", help="extend a finished clip (confirm first; billed)")
    p.add_argument("--task-id", required=True, help="completed task to extend")
    p.add_argument("--json", default=None, help="extra fields (prompt, etc.) as a JSON object")
    p.set_defaults(func=cmd_extend)

    p = sub.add_parser("lip-sync", help="lip-sync a video (confirm first; billed)")
    p.add_argument("--json", required=True, help="lip-sync spec as a JSON object")
    p.set_defaults(func=cmd_lip_sync)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
