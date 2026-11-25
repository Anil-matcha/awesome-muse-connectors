#!/usr/bin/env python3
"""Minimal Runway developer API CLI for the muse-connectors runway skill.

Auth: loads the per-user `custom.runway` credential (API secret from
dev.runwayml.com) as a surrogate via the bundled dynamic_credentials
helper. The real secret never touches this script: the runtime swaps the
surrogate on approved egress, only to api.dev.runwayml.com, and the CLI
sends `Authorization: Bearer <secret>` PLUS the mandatory
`X-Runway-Version: 2024-11-06` header on EVERY request.

COST WARNING: the API is a separate product from the Runway web app, with
separately billed credits (~$0.01/credit) and no free API tier. Poll no
more than once every 5 seconds.

ENDPOINT NOTE: text_to_video, image_to_video, and tasks/{id} are per the
research dossier. The upscale and lip_sync paths below implement dossier
capabilities but exact paths were not pinned in the dossier; verify against
docs.dev.runwayml.com if they 404 before live use.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.runway"
ALLOWED_HOSTS = ("api.dev.runwayml.com",)
BASE = "https://api.dev.runwayml.com/v1"
RUNWAY_VERSION = "2024-11-06"  # mandatory on every request

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


def api_secret() -> str:
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
    req.add_header("Authorization", f"Bearer {api_secret()}")
    req.add_header("X-Runway-Version", RUNWAY_VERSION)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", body.get("message", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: Runway returned HTTP {exc.code}: {msg}")
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


def _summarize_task(t: dict) -> dict:
    return {
        "id": t.get("id"), "status": t.get("status"),
        "createdAt": t.get("createdAt"), "output": t.get("output"),
        "failure": t.get("failure"), "failureCode": t.get("failureCode"),
    }


def cmd_auth(_args):
    # Runway has no documented zero-cost probe in the dossier; auth verifies
    # the credential is collected and well-formed. First generation spends
    # API credits.
    secret = api_secret()
    if not secret:
        sys.exit("error: empty credential")
    print(json.dumps({"ok": True, "version_header": RUNWAY_VERSION,
                      "note": "no zero-cost auth probe documented; auth checks "
                              "configuration only. First call spends API credits."},
                     indent=2))


def cmd_text_to_video(args):
    payload = {"promptText": args.prompt}
    if args.model:
        payload["model"] = args.model
    payload.update(_parse_json_arg(args.json))
    result = call("POST", "/text_to_video", payload=payload)
    t = result if isinstance(result, dict) else {}
    print(json.dumps(_summarize_task(t), indent=2))
    print(f"poll with: bin/runway.py task-status --id {t.get('id')} (no faster than every 5s)",
          file=sys.stderr)


def cmd_image_to_video(args):
    payload = {"promptText": args.prompt, "image": args.image}
    if args.model:
        payload["model"] = args.model
    payload.update(_parse_json_arg(args.json))
    result = call("POST", "/image_to_video", payload=payload)
    t = result if isinstance(result, dict) else {}
    print(json.dumps(_summarize_task(t), indent=2))
    print(f"poll with: bin/runway.py task-status --id {t.get('id')} (no faster than every 5s)",
          file=sys.stderr)


def cmd_task_status(args):
    result = call("GET", f"/tasks/{args.id}")
    t = result if isinstance(result, dict) else {}
    print(json.dumps(_summarize_task(t), indent=2))
    status = t.get("status")
    if status == "SUCCEEDED":
        print("note: output URLs are temporary; download promptly.",
              file=sys.stderr)
    elif status == "FAILED":
        print(f"failure: {t.get('failure') or t.get('failureCode')}", file=sys.stderr)


def cmd_upscale(args):
    payload = {"videoUri": args.video_uri}
    payload.update(_parse_json_arg(args.json))
    result = call("POST", "/video_upscale", payload=payload)  # see ENDPOINT NOTE
    t = result if isinstance(result, dict) else {}
    print(json.dumps(_summarize_task(t), indent=2))
    print(f"poll with: bin/runway.py task-status --id {t.get('id')}", file=sys.stderr)


def cmd_lip_sync(args):
    payload = _parse_json_arg(args.json)
    if not payload:
        sys.exit("error: --json with the lip-sync spec is required "
                 "(video, script/audio, character, etc. per Runway docs)")
    result = call("POST", "/lip_sync", payload=payload)  # see ENDPOINT NOTE
    t = result if isinstance(result, dict) else {}
    print(json.dumps(_summarize_task(t), indent=2))
    print(f"poll with: bin/runway.py task-status --id {t.get('id')}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Runway API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify credential configuration (no spend)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("text-to-video", help="Gen-4/4.5 text-to-video (confirm first; API credits)")
    p.add_argument("--prompt", required=True)
    p.add_argument("--model", default=None, help="e.g. gen4.5; confirm current ids in Runway docs")
    p.add_argument("--json", default=None,
                   help="extra fields (ratio, duration, etc.) as a JSON object")
    p.set_defaults(func=cmd_text_to_video)

    p = sub.add_parser("image-to-video", help="image-to-video (confirm first; API credits)")
    p.add_argument("--prompt", required=True)
    p.add_argument("--image", required=True, help="input image URL or data URI")
    p.add_argument("--model", default=None)
    p.add_argument("--json", default=None, help="extra fields as a JSON object")
    p.set_defaults(func=cmd_image_to_video)

    p = sub.add_parser("task-status", help="poll a task (no faster than every 5s)")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_task_status)

    p = sub.add_parser("upscale", help="upscale a video (confirm first; API credits)")
    p.add_argument("--video-uri", required=True, help="source video URL")
    p.add_argument("--json", default=None, help="extra fields as a JSON object")
    p.set_defaults(func=cmd_upscale)

    p = sub.add_parser("lip-sync", help="lip-sync a video (confirm first; API credits)")
    p.add_argument("--json", required=True, help="lip-sync spec as a JSON object")
    p.set_defaults(func=cmd_lip_sync)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
