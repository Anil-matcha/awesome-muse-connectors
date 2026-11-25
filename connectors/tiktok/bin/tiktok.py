#!/usr/bin/env python3
"""TikTok API v2 CLI (read-only) for the muse-connectors tiktok skill.

Auth: OAuth 2.0. The user approves access through the secure credential
flow (credentials.request_api_access) and the runtime hands this script a
fresh Bearer token via the bundled dynamic_credentials helper. The real
token never touches this script: the runtime swaps the surrogate on
approved egress, only to open.tiktokapis.com.

IMPORTANT LIMITATION (approval-gated): TikTok requires app review and
approval before API access works at all, and most apps cannot post videos
without additional approval. This connector ships READ commands only
(profile, video list). Video posting is intentionally not shipped; see the
SKILL.md Operating Rules.

HONESTY NOTE: scope names and endpoint paths below are taken from
TikTok's public API v2 docs and have not been verified against a live
app, because verification itself needs an approved TikTok app. Treat
every scope and path as provisional until a live call succeeds.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.tiktok"
ALLOWED_HOSTS = ("open.tiktokapis.com",)
BASE = "https://open.tiktokapis.com"
CONNECT_GUIDANCE = (
    "not connected: approve TikTok access via the secure credential flow "
    "(credentials.request_api_access) as `custom.tiktok` (OAuth 2.0; your "
    "TikTok app must pass TikTok's app review for API access to work at "
    "all), then retry."
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
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME,
                                 allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        if "missing" in str(exc) or "surrogate" in str(exc):
            sys.exit(CONNECT_GUIDANCE)
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            msg = raw[:500]
        except Exception:
            msg = str(exc)
        sys.exit(f"error: tiktok returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    err = body.get("error", {})
    if err.get("code") != "ok":
        sys.exit(f"error: tiktok api: {err.get('code')}: {err.get('message')}")
    return body.get("data", {})


USER_FIELDS = ("open_id,union_id,avatar_url,avatar_url_100,avatar_url_200,"
               "display_name,follower_count,following_count,likes_count,"
               "video_count")
VIDEO_FIELDS = ("id,create_time,cover_image_url,share_url,"
                "video_description,duration,like_count,comment_count,"
                "share_count,view_count")


def cmd_auth(args):
    data = call("GET", f"/v2/user/info/?fields=open_id,display_name")
    user = data.get("user", {})
    print(json.dumps({"ok": True,
                      "open_id": user.get("open_id"),
                      "display_name": user.get("display_name")}, indent=2))


def cmd_me(args):
    data = call("GET", f"/v2/user/info/?fields={USER_FIELDS}")
    print(json.dumps(data.get("user", {}), indent=2))


def cmd_videos(args):
    payload = {"max_count": args.limit}
    if args.cursor:
        payload["cursor"] = args.cursor
    data = call("POST", f"/v2/video/list/?fields={VIDEO_FIELDS}", payload)
    videos = [{"id": v.get("id"), "create_time": v.get("create_time"),
               "video_description": v.get("video_description"),
               "duration": v.get("duration"),
               "like_count": v.get("like_count"),
               "comment_count": v.get("comment_count"),
               "share_count": v.get("share_count"),
               "view_count": v.get("view_count"),
               "cover_image_url": v.get("cover_image_url"),
               "share_url": v.get("share_url")}
              for v in data.get("videos", [])]
    out = {"videos": videos}
    if data.get("has_more"):
        out["cursor"] = data.get("cursor")
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="TikTok API v2 CLI, read-only (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the OAuth token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("me", help="authorized user's profile")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("videos", help="list the user's videos")
    p.add_argument("--limit", type=int, default=20,
                   help="max_count per page (TikTok caps this)")
    p.add_argument("--cursor", default=None,
                   help="page cursor from a previous call")
    p.set_defaults(func=cmd_videos)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
