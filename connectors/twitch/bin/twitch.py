#!/usr/bin/env python3
"""Minimal Twitch Helix API CLI for the muse-connectors twitch skill.

Auth: loads the per-user `custom.twitch` OAuth token as a surrogate via the
bundled dynamic_credentials helper (sent as `Authorization: Bearer`).
Every Helix call ALSO needs a `Client-Id` header, which comes from the
user's Twitch app registration and is passed with --client-id.

Per the verified research dossier, all endpoints below live under
https://api.twitch.tv/helix.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.twitch"
ALLOWED_HOSTS = ("api.twitch.tv",)
API = "https://api.twitch.tv/helix"

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


def call(client_id: str, method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    # Helix requires the Client-Id header alongside the bearer token.
    req.add_header("Client-Id", client_id)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: twitch returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def profile_of(u: dict) -> dict:
    return {
        "id": u.get("id"),
        "login": u.get("login"),
        "display_name": u.get("display_name"),
        "type": u.get("type"),
        "broadcaster_type": u.get("broadcaster_type"),
        "description": (u.get("description") or "")[:200],
        "view_count": u.get("view_count"),
        "created_at": u.get("created_at"),
    }


def cmd_auth(args):
    result = call(args.client_id, "GET", "/users")
    users = result.get("data", [])
    if not users:
        sys.exit("error: twitch returned no user for this token")
    me = users[0]
    print(json.dumps({"ok": True, **profile_of(me)}, indent=2))


def cmd_user(args):
    params = {"login": args.login} if args.login else None
    result = call(args.client_id, "GET", "/users", params=params)
    print(json.dumps([profile_of(u) for u in result.get("data", [])], indent=2))


def cmd_followers(args):
    result = call(
        args.client_id, "GET", "/channels/followers",
        params={"broadcaster_id": args.broadcaster_id, "first": args.limit},
    )
    out = [
        {"user_id": f.get("user_id"), "user_login": f.get("user_login"),
         "followed_at": f.get("followed_at")}
        for f in result.get("data", [])
    ]
    print(json.dumps({"total": result.get("total"), "followers": out}, indent=2))


def cmd_stream(args):
    result = call(
        args.client_id, "GET", "/streams",
        params={"user_login": args.user_login},
    )
    streams = result.get("data", [])
    if not streams:
        print(json.dumps({"live": False, "user_login": args.user_login}, indent=2))
        return
    s = streams[0]
    print(json.dumps({
        "live": True,
        "user_login": s.get("user_login"),
        "title": s.get("title"),
        "game_name": s.get("game_name"),
        "viewer_count": s.get("viewer_count"),
        "started_at": s.get("started_at"),
        "language": s.get("language"),
    }, indent=2))


def cmd_videos(args):
    result = call(
        args.client_id, "GET", "/videos",
        params={"user_id": args.user_id, "first": args.limit},
    )
    out = [
        {"id": v.get("id"), "title": v.get("title"), "type": v.get("type"),
         "url": v.get("url"), "view_count": v.get("view_count"),
         "duration": v.get("duration"), "created_at": v.get("created_at")}
        for v in result.get("data", [])
    ]
    print(json.dumps(out, indent=2))


def cmd_channel_update(args):
    payload = {}
    if args.title is not None:
        payload["title"] = args.title
    if args.game_id is not None:
        payload["game_id"] = args.game_id
    if not payload:
        sys.exit("error: nothing to update; pass --title and/or --game-id")
    call(args.client_id, "POST", "/channels",
         params={"broadcaster_id": args.broadcaster_id}, payload=payload)
    print(json.dumps({"ok": True, "updated": payload}, indent=2))


def cmd_clip_create(args):
    params = {"broadcaster_id": args.broadcaster_id}
    if args.has_delay:
        params["has_delay"] = "true"
    result = call(args.client_id, "POST", "/clips", params=params)
    clips = result.get("data", [])
    if not clips:
        sys.exit("error: twitch returned no clip data")
    print(json.dumps({"ok": True, "id": clips[0].get("id"),
                      "edit_url": clips[0].get("edit_url")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Twitch Helix API CLI (muse-connectors)")
    parser.add_argument("--client-id", required=True,
                        help="Twitch app client id (Developer Console); sent as Client-Id header")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the token (returns own profile)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("user", help="channel profile (own, or --login for another)")
    p.add_argument("--login", default=None, help="channel login name; omit for own profile")
    p.set_defaults(func=cmd_user)

    p = sub.add_parser("followers", help="follower count + recent followers")
    p.add_argument("--broadcaster-id", required=True, help="numeric id from `user`")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_followers)

    p = sub.add_parser("stream", help="live status and viewer count")
    p.add_argument("--user-login", required=True)
    p.set_defaults(func=cmd_stream)

    p = sub.add_parser("videos", help="past broadcasts and clips")
    p.add_argument("--user-id", required=True, help="numeric id from `user`")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_videos)

    p = sub.add_parser("channel-update", help="update channel title/game (confirm first)")
    p.add_argument("--broadcaster-id", required=True, help="numeric id from `user`")
    p.add_argument("--title", default=None)
    p.add_argument("--game-id", default=None, help="Twitch game/category id")
    p.set_defaults(func=cmd_channel_update)

    p = sub.add_parser("clip-create", help="create a clip of the live broadcast (confirm first)")
    p.add_argument("--broadcaster-id", required=True, help="numeric id from `user`")
    p.add_argument("--has-delay", action="store_true",
                   help="delay the clip to mark where it was created")
    p.set_defaults(func=cmd_clip_create)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
