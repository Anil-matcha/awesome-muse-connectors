#!/usr/bin/env python3
"""Minimal Pexels API CLI for the muse-connectors Pexels skill.

Auth: API key loaded as a surrogate for `custom.pexels` via the bundled
dynamic_credentials helper. The key is sent VERBATIM in the Authorization
header with NO Bearer prefix (`Authorization: YOUR_API_KEY`), per Pexels'
docs; the placement is resolved by the helper from the credential config.
The real key never touches this script: the runtime swaps the surrogate on
approved egress, only to api.pexels.com.

The Pexels API is read-only: this CLI has no write commands.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.pexels"
ALLOWED_HOSTS = ("api.pexels.com",)
API = "https://api.pexels.com"

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


def credential_error(exc: Exception) -> None:
    sys.exit(
        "error: no stored credential for custom.pexels "
        f"({exc}). To connect, ask Muse to connect a Pexels API key "
        "(free at pexels.com/api) via the secure credential flow, then retry."
    )


def api_error(exc: urllib.error.HTTPError) -> None:
    try:
        body = json.loads(exc.read().decode("utf-8", errors="replace"))
        msg = body.get("error") or str(exc)
    except Exception:
        msg = str(exc)
    sys.exit(f"error: pexels returned HTTP {exc.code}: {msg}")


def call(path: str, params: dict | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, method="GET")
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except (DynamicCredentialError, OSError) as exc:
        credential_error(exc)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        api_error(exc)
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def slim_photo(p: dict) -> dict:
    return {
        "id": p.get("id"),
        "photographer": p.get("photographer"),
        "photographer_url": p.get("photographer_url"),
        "alt": p.get("alt"),
        "url": p.get("url"),
        "src": p.get("src"),
    }


def slim_video(v: dict) -> dict:
    files = [
        {"link": f.get("link"), "width": f.get("width"),
         "height": f.get("height"), "quality": f.get("quality")}
        for f in (v.get("video_files") or [])
    ]
    return {
        "id": v.get("id"),
        "user": (v.get("user") or {}).get("name"),
        "url": v.get("url"),
        "duration": v.get("duration"),
        "image": v.get("image"),
        "video_files": files,
    }


def cmd_auth(_args):
    result = call("/v1/curated", {"per_page": 1})
    print(json.dumps({"ok": True, "total_results": result.get("total_results")}, indent=2))


def cmd_search(args):
    result = call("/v1/search", {"query": args.query, "orientation": args.orientation,
                                 "size": args.size, "per_page": args.per_page,
                                 "page": args.page})
    print(json.dumps([slim_photo(p) for p in result.get("photos", [])], indent=2))


def cmd_curated(args):
    result = call("/v1/curated", {"per_page": args.per_page, "page": args.page})
    print(json.dumps([slim_photo(p) for p in result.get("photos", [])], indent=2))


def cmd_photo(args):
    print(json.dumps(slim_photo(call(f"/v1/photos/{args.id}")), indent=2))


def cmd_search_videos(args):
    result = call("/videos/search", {"query": args.query, "per_page": args.per_page,
                                     "page": args.page})
    print(json.dumps([slim_video(v) for v in result.get("videos", [])], indent=2))


def cmd_popular_videos(args):
    result = call("/videos/popular", {"per_page": args.per_page, "page": args.page})
    print(json.dumps([slim_video(v) for v in result.get("videos", [])], indent=2))


def cmd_video(args):
    print(json.dumps(slim_video(call(f"/videos/{args.id}")), indent=2))


def cmd_collection(args):
    result = call(f"/v1/collections/{args.id}",
                  {"per_page": args.per_page, "page": args.page})
    print(json.dumps({
        "id": result.get("id"),
        "title": result.get("title"),
        "photos": [slim_photo(p) for p in result.get("media", [])],
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Pexels API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("search", help="search photos")
    p.add_argument("--query", required=True)
    p.add_argument("--orientation", default=None, help="landscape, portrait, square")
    p.add_argument("--size", default=None, help="large, medium, small")
    p.add_argument("--per-page", default=None)
    p.add_argument("--page", default=None)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("curated", help="trending photos")
    p.add_argument("--per-page", default=None)
    p.add_argument("--page", default=None)
    p.set_defaults(func=cmd_curated)

    p = sub.add_parser("photo", help="one photo's details")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_photo)

    p = sub.add_parser("search-videos", help="search videos")
    p.add_argument("--query", required=True)
    p.add_argument("--per-page", default=None)
    p.add_argument("--page", default=None)
    p.set_defaults(func=cmd_search_videos)

    p = sub.add_parser("popular-videos", help="popular videos")
    p.add_argument("--per-page", default=None)
    p.add_argument("--page", default=None)
    p.set_defaults(func=cmd_popular_videos)

    p = sub.add_parser("video", help="one video's details")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_video)

    p = sub.add_parser("collection", help="contents of a collection")
    p.add_argument("--id", required=True)
    p.add_argument("--per-page", default=None)
    p.add_argument("--page", default=None)
    p.set_defaults(func=cmd_collection)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
