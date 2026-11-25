#!/usr/bin/env python3
"""Minimal Elai API CLI for the muse-connectors elai skill.

Auth: loads the per-user `custom.elai` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to apis.elai.io.
Auth is `Authorization: Bearer <API_TOKEN>`.

Rendering is async and credit-consuming: `render` submits the job and
`render-status` polls it. Both are confirmation-gated (see SKILL.md).
Custom-avatar footage submission and WebRTC real-time streaming are out of
CLI scope.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.elai"
ALLOWED_HOSTS = ("apis.elai.io",)
API = "https://apis.elai.io/api/v1"

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


def call(method: str, path: str, payload: dict | None = None):
    """Call the Elai API."""
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: elai returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def _no_credential_exit():
    print(json.dumps({
        "ok": False,
        "error": "no credential stored for custom.elai",
        "connect": ("store an Elai API token as custom.elai via the secure "
                    "credential flow (credentials.request_api_access), then rerun auth"),
    }, indent=2))
    sys.exit(1)


def cmd_auth(_args):
    try:
        result = call("GET", "/avatars")
    except DynamicCredentialError:
        _no_credential_exit()
    except Exception as exc:  # authd unavailable or network down: no traceback
        print(json.dumps({"ok": False, "error": f"status check failed: {exc}"},
                         indent=2))
        sys.exit(1)
    avatars = result if isinstance(result, list) else result.get("avatars", [])
    count = len(avatars) if isinstance(avatars, list) else None
    print(json.dumps({"ok": True, "avatars": count}, indent=2))


def _list_items(result, key):
    if isinstance(result, list):
        return result
    items = result.get(key, result)
    return items if isinstance(items, list) else []


def cmd_avatars(_args):
    result = call("GET", "/avatars")
    avatars = [{"code": a.get("code"), "name": a.get("name"),
                 "gender": a.get("gender"), "status": a.get("status")}
                for a in _list_items(result, "avatars")]
    print(json.dumps(avatars, indent=2))


def cmd_videos(_args):
    result = call("GET", "/videos")
    videos = [{"id": v.get("_id") or v.get("id"), "name": v.get("name"),
               "status": v.get("status")} for v in _list_items(result, "videos")]
    print(json.dumps(videos, indent=2))


def _video_summary(video):
    return {
        "id": video.get("_id") or video.get("id"),
        "name": video.get("name"),
        "status": video.get("status"),
        "url": video.get("url"),
        "thumbnail": video.get("thumbnail"),
    }


def cmd_video_get(args):
    result = call("GET", f"/videos/{args.id}")
    video = result.get("video") or result
    print(json.dumps(_video_summary(video), indent=2))


def cmd_render(args):
    result = call("POST", f"/videos/render/{args.id}", payload={})
    print(json.dumps({
        "ok": True,
        "video_id": args.id,
        "status": result.get("status", "submitted"),
        "response": result,
    }, indent=2))


def cmd_render_status(args):
    result = call("GET", f"/videos/{args.id}")
    video = result.get("video") or result
    print(json.dumps(_video_summary(video), indent=2))


def main():
    parser = argparse.ArgumentParser(description="Elai avatar video API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="status check: list avatars and confirm the token works")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("avatars", help="list available avatars")
    p.set_defaults(func=cmd_avatars)

    p = sub.add_parser("videos", help="list your videos")
    p.set_defaults(func=cmd_videos)

    p = sub.add_parser("video-get", help="details for a single video, including render status")
    p.add_argument("--id", required=True, help="video id")
    p.set_defaults(func=cmd_video_get)

    p = sub.add_parser("render", help="submit a render for a video (CREDIT-CONSUMING, CONFIRMATION-GATED)")
    p.add_argument("--id", required=True, help="video id to render")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("render-status", help="poll render status for a video")
    p.add_argument("--id", required=True, help="video id")
    p.set_defaults(func=cmd_render_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
