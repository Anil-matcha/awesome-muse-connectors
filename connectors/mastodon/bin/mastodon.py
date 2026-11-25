#!/usr/bin/env python3
"""Minimal Mastodon API CLI for the muse-connectors mastodon skill.

Auth: loads the per-user `custom.mastodon` OAuth token as a surrogate via the
bundled dynamic_credentials helper (sent as `Authorization: Bearer`).

Mastodon instances are per-user, so --host is required on every command
(e.g. https://mastodon.social). The allowed-hosts check is built from the
parsed hostname at runtime, n8n-connector style.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.mastodon"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        add_surrogate_to_request,
        ensure_allowed_url,
        read_json_response,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def base_and_hosts(host: str) -> tuple[str, tuple[str, ...]]:
    if not (host.startswith("http://") or host.startswith("https://")):
        sys.exit("error: --host must start with http:// or https://")
    host = host.rstrip("/")
    parsed = urllib.parse.urlparse(host)
    return host + "/api/v1", (parsed.hostname,)


def authed_request(host: str, method: str, path: str, params=None, payload=None,
                   raw_body=None, content_type=None):
    base, hosts = base_and_hosts(host)
    url = base + path
    data = raw_body
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    if content_type:
        headers["Content-Type"] = content_type
    ensure_allowed_url(url, allowed_hosts=hosts)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=hosts)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    return req


def call(host: str, method: str, path: str, params=None, payload=None) -> dict:
    req = authed_request(host, method, path, params=params, payload=payload)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: mastodon returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def own_id(host: str) -> str:
    return str(call(host, "GET", "/accounts/verify_credentials")["id"])


def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html or "")
    return text.strip()


def cmd_verify(args):
    me = call(args.host, "GET", "/accounts/verify_credentials")
    print(json.dumps({
        "ok": True,
        "id": me.get("id"),
        "username": me.get("username"),
        "acct": me.get("acct"),
        "display_name": me.get("display_name"),
        "followers_count": me.get("followers_count"),
        "following_count": me.get("following_count"),
        "statuses_count": me.get("statuses_count"),
        "url": me.get("url"),
    }, indent=2))


def cmd_my_posts(args):
    me = own_id(args.host)
    result = call(args.host, "GET", f"/accounts/{me}/statuses",
                  params={"limit": args.limit})
    out = [
        {"id": s.get("id"), "created_at": s.get("created_at"),
         "text": strip_html(s.get("content", ""))[:400],
         "url": s.get("url"), "visibility": s.get("visibility"),
         "replies_count": s.get("replies_count"),
         "reblogs_count": s.get("reblogs_count"),
         "favourites_count": s.get("favourites_count")}
        for s in result
    ]
    print(json.dumps(out, indent=2))


def cmd_followers(args):
    me = own_id(args.host)
    result = call(args.host, "GET", f"/accounts/{me}/followers",
                  params={"limit": args.limit})
    out = [
        {"id": f.get("id"), "username": f.get("username"),
         "acct": f.get("acct"), "display_name": f.get("display_name")}
        for f in result
    ]
    print(json.dumps(out, indent=2))


def cmd_post(args):
    text = args.text
    if len(text) > 500:
        sys.exit(f"error: toot is {len(text)} chars; mastodon limit is 500")
    payload = {"status": text, "visibility": args.visibility}
    if args.scheduled_at:
        payload["scheduled_at"] = args.scheduled_at
    if args.media_ids:
        payload["media_ids"] = [m.strip() for m in args.media_ids.split(",") if m.strip()]
    result = call(args.host, "POST", "/statuses", payload=payload)
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "url": result.get("url"),
                      "scheduled_at": result.get("scheduled_at")}, indent=2))


def encode_multipart(file_path: str, description: str | None):
    boundary = "museconnectors-" + uuid.uuid4().hex
    parts = []
    if description:
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="description"\r\n\r\n{description}\r\n'.encode("utf-8")
        )
    filename = os.path.basename(file_path)
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(file_path, "rb") as fh:
        file_bytes = fh.read()
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode("utf-8")
        + file_bytes + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def cmd_media_upload(args):
    if not os.path.isfile(args.file):
        sys.exit(f"error: no file at {args.file}")
    body, content_type = encode_multipart(args.file, args.description)
    req = authed_request(args.host, "POST", "/media", raw_body=body,
                         content_type=content_type)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body_json = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body_json.get("error", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: mastodon returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "type": result.get("type")}, indent=2))


def add_host_arg(p):
    p.add_argument("--host", required=True,
                   help="your mastodon instance, e.g. https://mastodon.social")


def main():
    parser = argparse.ArgumentParser(description="Mastodon API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("verify", help="verify the token (own profile)")
    add_host_arg(p)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("my-posts", help="list own recent toots")
    add_host_arg(p)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_my_posts)

    p = sub.add_parser("followers", help="list own followers")
    add_host_arg(p)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_followers)

    p = sub.add_parser("post", help="publish a toot (confirm first)")
    add_host_arg(p)
    p.add_argument("--text", required=True, help="toot text, max 500 chars")
    p.add_argument("--visibility", default="public",
                   choices=["public", "unlisted", "private", "direct"])
    p.add_argument("--scheduled-at", default=None,
                   help="ISO 8601 time for native scheduling, e.g. 2026-09-17T09:00:00Z")
    p.add_argument("--media-ids", default=None,
                   help="comma-separated media ids from media-upload")
    p.set_defaults(func=cmd_post)

    p = sub.add_parser("media-upload", help="upload an image for a toot")
    add_host_arg(p)
    p.add_argument("--file", required=True, help="path to the image file")
    p.add_argument("--description", default=None, help="alt text")
    p.set_defaults(func=cmd_media_upload)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
