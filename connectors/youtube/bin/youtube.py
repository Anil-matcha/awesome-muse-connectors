#!/usr/bin/env python3
"""YouTube Data API v3 CLI for the muse-connectors youtube skill.

Reads (channel, video, search, playlist items) and writes (video upload,
top-level comments).

Auth: OAuth 2.0. The user approves access through the secure credential
flow (credentials.request_api_access) and the runtime hands this script a
fresh Bearer token via the bundled dynamic_credentials helper. The real
token never touches this script: the runtime swaps the surrogate on
approved egress, only to www.googleapis.com.

Scopes requested at approval (from Google's public OAuth scope docs):
  https://www.googleapis.com/auth/youtube.readonly   (reads)
  https://www.googleapis.com/auth/youtube.upload     (video uploads)
  https://www.googleapis.com/auth/youtube.force-ssl  (comments;
      per the commentThreads.insert docs this is the required scope)

Writes (upload, comment) require an exact --confirm string echoed by the
CLI, on every call.

HONESTY NOTE: endpoint paths and the scope list are taken from Google's
public API docs and have not yet been verified in a live flow. The
upload quota cost (~1,600 units) is from secondary sources, not Google's
own docs; commentThreads.insert costs 50 units per Google's docs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.youtube"
ALLOWED_HOSTS = ("www.googleapis.com",)
BASE = "https://www.googleapis.com"
CONNECT_GUIDANCE = (
    "not connected: approve YouTube access via the secure credential flow "
    "(credentials.request_api_access) as `custom.youtube` (OAuth 2.0 with "
    "the youtube.readonly, youtube.upload, and youtube.force-ssl scopes), "
    "then retry."
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


def error_exit(exc, provider="YouTube"):
    """Exit with the provider's own error message when available."""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = (body.get("error") or {}).get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: {provider} returned HTTP {exc.code}: {msg}")
    sys.exit(f"error: request failed: {exc}")


def authed_request(url: str, data=None, headers: dict | None = None,
                   method: str | None = None) -> urllib.request.Request:
    """Build a request with the OAuth surrogate attached (Bearer)."""
    req = urllib.request.Request(url, data=data,
                                 headers=headers or {}, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME,
                                 allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        if "missing" in str(exc) or "surrogate" in str(exc):
            sys.exit(CONNECT_GUIDANCE)
        sys.exit(f"error: credential problem: {exc}")
    return req


def call(method: str, path: str, payload: dict | None = None) -> dict:
    """JSON call against the YouTube Data API v3 base."""
    url = BASE + path
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = authed_request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except Exception as exc:  # HTTPError and network-level failures
        error_exit(exc)


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def cmd_auth(_args):
    # 1-unit endpoint; verifies the OAuth token belongs to a channel.
    result = call("GET", "/youtube/v3/channels?part=id,snippet&mine=true")
    items = result.get("items", [])
    channel = items[0] if items else {}
    print(json.dumps({"ok": True, "channel_id": channel.get("id"),
                      "title": (channel.get("snippet") or {}).get("title")},
                     indent=2))


def cmd_channel(args):
    result = call(
        "GET",
        f"/youtube/v3/channels?part={urllib.parse.quote('snippet,statistics')}"
        f"&id={urllib.parse.quote(args.id)}")
    items = result.get("items", [])
    out = []
    for c in items:
        snippet, stats = c.get("snippet", {}), c.get("statistics", {})
        out.append({"id": c.get("id"), "title": snippet.get("title"),
                    "description": (snippet.get("description") or "")[:200],
                    "subscribers": stats.get("subscriberCount"),
                    "views": stats.get("viewCount"),
                    "videos": stats.get("videoCount")})
    print(json.dumps(out, indent=2))


def cmd_video(args):
    result = call(
        "GET",
        f"/youtube/v3/videos?part={urllib.parse.quote('snippet,statistics')}"
        f"&id={urllib.parse.quote(args.id)}")
    items = result.get("items", [])
    out = []
    for v in items:
        snippet, stats = v.get("snippet", {}), v.get("statistics", {})
        out.append({"id": v.get("id"), "title": snippet.get("title"),
                    "channel": snippet.get("channelTitle"),
                    "published": snippet.get("publishedAt"),
                    "views": stats.get("viewCount"),
                    "likes": stats.get("likeCount"),
                    "comments": stats.get("commentCount")})
    print(json.dumps(out, indent=2))


def cmd_search(args):
    result = call(
        "GET",
        "/youtube/v3/search?part=snippet&type=video"
        f"&q={urllib.parse.quote(args.query)}&maxResults={args.limit}")
    out = [
        {"id": (i.get("id") or {}).get("videoId"),
         "title": (i.get("snippet") or {}).get("title"),
         "channel": (i.get("snippet") or {}).get("channelTitle"),
         "published": (i.get("snippet") or {}).get("publishedAt")}
        for i in result.get("items", [])
    ]
    print(json.dumps(out, indent=2))


def cmd_playlist_items(args):
    result = call(
        "GET",
        "/youtube/v3/playlistItems?part=snippet"
        f"&playlistId={urllib.parse.quote(args.playlist_id)}"
        f"&maxResults={args.limit}")
    out = [
        {"id": (i.get("snippet") or {}).get("resourceId", {}).get("videoId"),
         "title": (i.get("snippet") or {}).get("title"),
         "position": (i.get("snippet") or {}).get("position")}
        for i in result.get("items", [])
    ]
    print(json.dumps(out, indent=2))


def my_channel_id() -> str:
    """Resolve the authenticated user's channel ID (1 quota unit)."""
    result = call("GET", "/youtube/v3/channels?part=id&mine=true")
    items = result.get("items", [])
    if not items or not items[0].get("id"):
        sys.exit("error: could not resolve the authenticated channel ID")
    return items[0]["id"]


def cmd_upload(args):
    if not os.path.isfile(args.file):
        sys.exit(f"error: no such file: {args.file}")
    size = os.path.getsize(args.file)
    if size == 0:
        sys.exit("error: refusing to upload an empty file")
    privacy = args.privacy
    expected = f'upload "{args.file}" as {privacy} video "{args.title}"'
    need_confirm(
        args, expected,
        f"uploading {args.file} ({size} bytes) to the authenticated "
        f"YouTube channel as a {privacy} video titled {args.title!r}.")
    metadata = {"snippet": {"title": args.title,
                            "description": args.description or ""},
                "status": {"privacyStatus": privacy}}
    init_url = (f"{BASE}/upload/youtube/v3/videos?uploadType=resumable"
                f"&part={urllib.parse.quote('snippet,status')}")
    headers = {"Content-Type": "application/json; charset=UTF-8",
               "X-Upload-Content-Length": str(size),
               "X-Upload-Content-Type": "application/octet-stream"}
    req = authed_request(init_url, data=json.dumps(metadata).encode("utf-8"),
                         headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            session_uri = resp.headers.get("Location")
    except Exception as exc:
        error_exit(exc)
    if not session_uri:
        sys.exit("error: upload session started but no session URI was "
                 "returned")
    # Step 2: PUT the video bytes to the session URI (single chunk).
    with open(args.file, "rb") as fh:
        data = fh.read()
    req = authed_request(session_uri, data=data,
                         headers={"Content-Type": "application/octet-stream"},
                         method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            result = read_json_response(resp)
    except Exception as exc:
        error_exit(exc)
    print(json.dumps({"ok": True, "video_id": result.get("id"),
                      "title": (result.get("snippet") or {}).get("title"),
                      "privacy": privacy}, indent=2))


def cmd_comment(args):
    expected = (f'post comment on video {args.video_id}: '
                f'"{args.text[:60]}"')
    need_confirm(
        args, expected,
        f"posting a top-level comment on video {args.video_id} as the "
        "authenticated channel; it is public immediately.")
    channel_id = my_channel_id()
    result = call(
        "POST", "/youtube/v3/commentThreads?part=snippet",
        {"snippet": {"channelId": channel_id,
                     "videoId": args.video_id,
                     "topLevelComment": {
                         "snippet": {"textOriginal": args.text}}}})
    snippet = (result.get("snippet") or {}).get("topLevelComment", {}
                                                ).get("snippet", {})
    print(json.dumps({"ok": True, "comment_id": result.get("id"),
                      "video_id": args.video_id,
                      "text": snippet.get("textOriginal")}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Data API v3 CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the OAuth token (1 quota unit)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("channel", help="show a channel (1 quota unit)")
    p.add_argument("--id", required=True, help="channel ID")
    p.set_defaults(func=cmd_channel)

    p = sub.add_parser("video", help="show a video (1 quota unit)")
    p.add_argument("--id", required=True, help="video ID")
    p.set_defaults(func=cmd_video)

    p = sub.add_parser("search", help="search videos (100 quota units)")
    p.add_argument("--query", required=True)
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("playlist-items",
                       help="list playlist items (1 quota unit)")
    p.add_argument("--playlist-id", required=True)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_playlist_items)

    p = sub.add_parser("upload",
                       help="upload a video file (needs --confirm)")
    p.add_argument("--file", required=True, help="video file to upload")
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--privacy", default="private",
                   choices=("private", "public", "unlisted"))
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("comment",
                       help="post a top-level comment (needs --confirm)")
    p.add_argument("--video-id", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_comment)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
