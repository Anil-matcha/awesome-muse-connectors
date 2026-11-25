#!/usr/bin/env python3
"""Spotify Web API CLI for the muse-connectors spotify skill.

Auth: OAuth 2.0 Authorization Code flow. The user approves access through
the secure credential flow (credentials.request_api_access) and the runtime
hands this script a fresh Bearer token via the bundled dynamic_credentials
helper. The real token never touches this script: the runtime swaps the
surrogate on approved egress, only to api.spotify.com.

Scopes requested at approval: user-read-private, user-read-email,
playlist-read-private, playlist-modify-private, playlist-modify-public,
user-top-read, user-library-read, user-library-modify.
HONESTY NOTE: this scope list and the endpoint paths below are taken from
Spotify's public Web API docs and have not yet been verified in a live
flow. If a command 403s, re-check the granted scopes.

Writes (playlist-create, playlist-add, save-track) require an exact
--confirm string echoed by the CLI, on every call.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.spotify"
ALLOWED_HOSTS = ("api.spotify.com",)
BASE = "https://api.spotify.com"
CONNECT_GUIDANCE = (
    "not connected: approve Spotify access via the secure credential flow "
    "(credentials.request_api_access) as `custom.spotify` (OAuth "
    "Authorization Code flow with the scopes listed in this skill), then "
    "retry."
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
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            err = body.get("error", {})
            msg = err.get("message", str(exc)) if isinstance(err, dict) else str(exc)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: spotify returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def slim_track(t: dict) -> dict:
    artists = [a.get("name") for a in t.get("artists", [])]
    return {"id": t.get("id"), "name": t.get("name"),
            "artists": artists,
            "album": (t.get("album") or {}).get("name"),
            "uri": t.get("uri")}


def cmd_auth(args):
    me = call("GET", "/v1/me")
    print(json.dumps({"ok": True,
                      "id": me.get("id"),
                      "display_name": me.get("display_name"),
                      "email": me.get("email")}, indent=2))


def cmd_me(args):
    me = call("GET", "/v1/me")
    print(json.dumps({"id": me.get("id"),
                      "display_name": me.get("display_name"),
                      "email": me.get("email"),
                      "country": me.get("country"),
                      "product": me.get("product"),
                      "followers": (me.get("followers") or {}).get("total")},
                     indent=2))


def cmd_playlists(args):
    result = call("GET", f"/v1/me/playlists?limit={args.limit}")
    items = [{"id": p.get("id"), "name": p.get("name"),
              "public": p.get("public"),
              "tracks_total": (p.get("tracks") or {}).get("total"),
              "owner": (p.get("owner") or {}).get("id")}
             for p in result.get("items", [])]
    print(json.dumps(items, indent=2))


def cmd_playlist_tracks(args):
    result = call("GET",
                  f"/v1/playlists/{args.playlist_id}/tracks?limit={args.limit}")
    items = [slim_track(i.get("track", {})) for i in result.get("items", [])]
    print(json.dumps(items, indent=2))


def cmd_top_tracks(args):
    result = call("GET", f"/v1/me/top/tracks?limit={args.limit}"
                         f"&time_range={args.time_range}")
    print(json.dumps([slim_track(t) for t in result.get("items", [])],
                     indent=2))


def cmd_top_artists(args):
    result = call("GET", f"/v1/me/top/artists?limit={args.limit}"
                         f"&time_range={args.time_range}")
    items = [{"id": a.get("id"), "name": a.get("name"),
              "genres": a.get("genres", [])[:5],
              "popularity": a.get("popularity")}
             for a in result.get("items", [])]
    print(json.dumps(items, indent=2))


def cmd_search(args):
    q = urllib.parse.quote(args.query)
    types = ",".join(args.types.split())
    result = call("GET",
                  f"/v1/search?q={q}&type={types}&limit={args.limit}")
    out = {}
    tracks = result.get("tracks", {}).get("items", [])
    if tracks:
        out["tracks"] = [slim_track(t) for t in tracks]
    for kind, key in (("artists", "artists"), ("albums", "albums"),
                      ("playlists", "playlists")):
        items = result.get(kind, {}).get("items", [])
        if items:
            out[key] = [{"id": i.get("id"), "name": i.get("name"),
                         "uri": i.get("uri")} for i in items]
    print(json.dumps(out, indent=2))


def cmd_playlist_create(args):
    me = call("GET", "/v1/me")
    user_id = me.get("id")
    expected = f'create playlist "{args.name}"'
    need_confirm(
        args, expected,
        f"creating a playlist named {args.name!r} in the user's Spotify "
        "library (a public one is visible to everyone).")
    result = call("POST", f"/v1/users/{user_id}/playlists",
                  {"name": args.name,
                   "description": args.description,
                   "public": args.public})
    print(json.dumps({"ok": True, "playlist_id": result.get("id"),
                      "name": result.get("name"),
                      "url": (result.get("external_urls") or {}).get("spotify")},
                     indent=2))


def cmd_playlist_add(args):
    uris = [u.strip() for u in args.uris.split(",") if u.strip()]
    if not uris:
        sys.exit("error: --uris needs at least one Spotify track URI")
    expected = f"add {len(uris)} track(s) to playlist {args.playlist_id}"
    need_confirm(
        args, expected,
        f"appending {len(uris)} track(s) to playlist {args.playlist_id}.")
    result = call("POST", f"/v1/playlists/{args.playlist_id}/tracks",
                  {"uris": uris})
    print(json.dumps({"ok": True,
                      "playlist_id": args.playlist_id,
                      "tracks_added": len(uris),
                      "snapshot_id": result.get("snapshot_id")}, indent=2))


def cmd_save_track(args):
    ids = ",".join(i.strip() for i in args.ids.split(",") if i.strip())
    if not ids:
        sys.exit("error: --ids needs at least one Spotify track ID")
    expected = f"save track(s) {ids} to your library"
    need_confirm(
        args, expected,
        "saving track(s) to the user's Liked Songs / library.")
    call("PUT", f"/v1/me/tracks?ids={urllib.parse.quote(ids)}")
    print(json.dumps({"ok": True, "saved": ids.split(",")}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Spotify Web API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the OAuth token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("me", help="current user's profile")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("playlists", help="list the user's playlists")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_playlists)

    p = sub.add_parser("playlist-tracks",
                       help="list tracks in a playlist")
    p.add_argument("--playlist-id", required=True)
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_playlist_tracks)

    p = sub.add_parser("top-tracks", help="user's top tracks")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--time-range", default="medium_term",
                   choices=("short_term", "medium_term", "long_term"))
    p.set_defaults(func=cmd_top_tracks)

    p = sub.add_parser("top-artists", help="user's top artists")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--time-range", default="medium_term",
                   choices=("short_term", "medium_term", "long_term"))
    p.set_defaults(func=cmd_top_artists)

    p = sub.add_parser("search", help="search Spotify")
    p.add_argument("--query", required=True)
    p.add_argument("--types", default="track artist album playlist",
                   help="space-separated types")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("playlist-create",
                       help="create a playlist (needs --confirm)")
    p.add_argument("--name", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--public", action="store_true",
                   help="make the playlist public (default: private)")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_playlist_create)

    p = sub.add_parser("playlist-add",
                       help="add tracks to a playlist (needs --confirm)")
    p.add_argument("--playlist-id", required=True)
    p.add_argument("--uris", required=True,
                   help="comma-separated Spotify track URIs")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_playlist_add)

    p = sub.add_parser("save-track",
                       help="save tracks to your library (needs --confirm)")
    p.add_argument("--ids", required=True,
                   help="comma-separated Spotify track IDs")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_save_track)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
