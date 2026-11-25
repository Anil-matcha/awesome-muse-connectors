#!/usr/bin/env python3
"""Minimal Unsplash API CLI for the muse-connectors Unsplash skill.

Auth: access key loaded as a surrogate for `custom.unsplash` via the bundled
dynamic_credentials helper. It is sent as `Authorization: Client-ID
YOUR_ACCESS_KEY` (with the Client-ID prefix), per Unsplash's docs; the
placement is resolved by the helper from the credential config. The real key
never touches this script: the runtime swaps the surrogate on approved
egress, only to api.unsplash.com.

Unsplash's guidelines REQUIRE hitting a photo's `download_location` URL
whenever the image is downloaded/used (it credits the photographer). The
`download` command does this automatically before saving the image bytes.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.unsplash"
ALLOWED_HOSTS = ("api.unsplash.com",)
API = "https://api.unsplash.com"

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
        "error: no stored credential for custom.unsplash "
        f"({exc}). To connect, ask Muse to connect an Unsplash access key "
        "(free developer app at unsplash.com/developers) via the secure "
        "credential flow, then retry."
    )


def api_error(exc: urllib.error.HTTPError) -> None:
    try:
        body = json.loads(exc.read().decode("utf-8", errors="replace"))
        errors = body.get("errors")
        msg = "; ".join(errors) if errors else str(exc)
    except Exception:
        msg = str(exc)
    sys.exit(f"error: unsplash returned HTTP {exc.code}: {msg}")


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
    user = p.get("user") or {}
    return {
        "id": p.get("id"),
        "description": p.get("description") or p.get("alt_description"),
        "photographer": user.get("name"),
        "photographer_username": user.get("username"),
        "urls": p.get("urls"),
        "links": p.get("links"),
    }


def cmd_auth(_args):
    result = call("/photos", {"per_page": 1})
    first = result[0] if isinstance(result, list) and result else {}
    print(json.dumps({"ok": True, "sample_photo_id": first.get("id")}, indent=2))


def cmd_search(args):
    result = call("/search/photos", {"query": args.query,
                                     "orientation": args.orientation,
                                     "per_page": args.per_page,
                                     "page": args.page})
    print(json.dumps({
        "total": result.get("total"),
        "photos": [slim_photo(p) for p in result.get("results", [])],
    }, indent=2))


def cmd_list(args):
    result = call("/photos", {"per_page": args.per_page, "page": args.page})
    photos = result if isinstance(result, list) else []
    print(json.dumps([slim_photo(p) for p in photos], indent=2))


def cmd_photo(args):
    print(json.dumps(slim_photo(call(f"/photos/{args.id}")), indent=2))


def cmd_user_photos(args):
    result = call(f"/users/{args.username}/photos",
                  {"per_page": args.per_page, "page": args.page})
    photos = result if isinstance(result, list) else []
    print(json.dumps([slim_photo(p) for p in photos], indent=2))


def cmd_topic(args):
    result = call(f"/topics/{args.id}/photos",
                  {"per_page": args.per_page, "page": args.page})
    photos = result if isinstance(result, list) else []
    print(json.dumps([slim_photo(p) for p in photos], indent=2))


def cmd_download(args):
    photo = call(f"/photos/{args.id}")
    links = photo.get("links") or {}
    download_location = links.get("download_location")
    if not download_location:
        sys.exit("error: photo has no download_location to credit")
    # Guideline requirement: hit download_location whenever the image is used.
    req = urllib.request.Request(download_location, method="GET")
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except (DynamicCredentialError, OSError) as exc:
        credential_error(exc)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read(1)
    except Exception as exc:
        sys.exit(f"error: download_location hit failed: {exc}")
    raw_url = (photo.get("urls") or {}).get("raw")
    if not raw_url:
        sys.exit("error: photo has no raw image URL")
    try:
        with urllib.request.urlopen(raw_url, timeout=60) as resp:
            image = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except Exception as exc:
        sys.exit(f"error: image download failed: {exc}")
    try:
        with open(args.out, "wb") as fh:
            fh.write(image)
    except OSError as exc:
        sys.exit(f"error: cannot write file: {exc}")
    user = photo.get("user") or {}
    print(json.dumps({
        "saved_to": args.out,
        "bytes": len(image),
        "content_type": content_type,
        "credit": f"Photo by {user.get('name')} on Unsplash",
        "download_location_credited": True,
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Unsplash API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("search", help="search photos")
    p.add_argument("--query", required=True)
    p.add_argument("--orientation", default=None, help="landscape, portrait, squarish")
    p.add_argument("--per-page", default=None)
    p.add_argument("--page", default=None)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("list", help="latest photos")
    p.add_argument("--per-page", default=None)
    p.add_argument("--page", default=None)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("photo", help="one photo's details")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_photo)

    p = sub.add_parser("user-photos", help="a photographer's photos")
    p.add_argument("--username", required=True)
    p.add_argument("--per-page", default=None)
    p.add_argument("--page", default=None)
    p.set_defaults(func=cmd_user_photos)

    p = sub.add_parser("topic", help="photos in a topic")
    p.add_argument("--id", required=True, help="topic id or slug")
    p.add_argument("--per-page", default=None)
    p.add_argument("--page", default=None)
    p.set_defaults(func=cmd_topic)

    p = sub.add_parser("download", help="download an image, crediting the photographer")
    p.add_argument("--id", required=True, help="photo id")
    p.add_argument("--out", required=True, help="local path to save the image")
    p.set_defaults(func=cmd_download)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
