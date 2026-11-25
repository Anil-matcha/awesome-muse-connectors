#!/usr/bin/env python3
"""GetYouTubeTranscript CLI for the muse-connectors getyoutubetranscript skill.

Read-only: YouTube transcripts, caption languages, search, a channel's latest
videos and playlist videos, from the GetYouTubeTranscript REST API
(https://getyoutubetranscript.com/api/v1, docs https://getyoutubetranscript.com/docs).

Auth: loads the per-user `custom.getyoutubetranscript` credential as a
surrogate via the bundled dynamic_credentials helper. The real API key never
touches this script: the runtime swaps the surrogate on approved egress, only
to getyoutubetranscript.com, in the `x-api-key` header.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.getyoutubetranscript"
ALLOWED_HOSTS = ("getyoutubetranscript.com",)
API = "https://getyoutubetranscript.com/api/v1"

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


def call_get(path: str, params: dict) -> dict:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "", False)})
    req = urllib.request.Request(API + path + ("?" + query if query else ""), headers={"Accept": "application/json"})
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        # Every API error is {"success": false, "code": ..., "message": ...}
        try:
            body = json.loads(exc.read().decode("utf-8", "replace"))
            msg = f"{body.get('code')}: {body.get('message')}"
        except Exception:
            msg = str(exc)
        sys.exit(f"error: GetYouTubeTranscript returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def emit(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def cmd_auth(_args):
    # /credits is free (no credit charged), so it is the status check.
    data = call_get("/credits", {}).get("data", {})
    emit({"ok": True, "credits": data})


def cmd_transcript(args):
    data = call_get(
        "/transcript",
        {"v": args.video, "language": args.language, "timestamps": "true" if args.timestamps else None},
    ).get("data", {})
    out = {k: data.get(k) for k in ("video_id", "title", "author_name", "language_code", "caption_type", "word_count")}
    if args.timestamps:
        out["segments"] = data.get("segments", [])
    else:
        out["transcript"] = data.get("transcript")
    emit(out)


def cmd_languages(args):
    emit(call_get("/transcript/languages", {"v": args.video}).get("data", {}))


def cmd_search(args):
    data = call_get("/search", {"q": args.query, "type": "video", "limit": args.limit}).get("data", {})
    emit([
        {"title": r.get("title"), "url": r.get("link"), "channel": (r.get("channel") or {}).get("name")}
        for r in data.get("video_results", [])[: args.limit]
    ])


def cmd_channel_latest(args):
    emit(call_get("/channel/latest", {"channel": args.channel}).get("data", {}))


def cmd_playlist(args):
    emit(call_get("/playlist", {"list": args.playlist, "continuation": args.continuation}).get("data", {}))


def main():
    parser = argparse.ArgumentParser(description="GetYouTubeTranscript CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection (free call)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("transcript", help="full transcript of one video")
    p.add_argument("--video", required=True, help="YouTube URL or 11-character video ID")
    p.add_argument("--language", help="caption language code, e.g. en")
    p.add_argument("--timestamps", action="store_true", help="return timed segments")
    p.set_defaults(func=cmd_transcript)

    p = sub.add_parser("languages", help="caption languages available for a video")
    p.add_argument("--video", required=True)
    p.set_defaults(func=cmd_languages)

    p = sub.add_parser("search", help="search YouTube videos")
    p.add_argument("--query", required=True)
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("channel-latest", help="a channel's latest videos")
    p.add_argument("--channel", required=True, help="channel ID, @handle or URL")
    p.set_defaults(func=cmd_channel_latest)

    p = sub.add_parser("playlist", help="videos in a playlist")
    p.add_argument("--playlist", required=True, help="playlist ID or URL")
    p.add_argument("--continuation", help="token from a previous page")
    p.set_defaults(func=cmd_playlist)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
