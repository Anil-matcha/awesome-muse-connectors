#!/usr/bin/env python3
"""Minimal Buzzsprout API CLI for the muse-connectors buzzsprout skill.

Auth: loads the per-user `custom.buzzsprout` credential as a surrogate via
the bundled dynamic_credentials helper. Buzzsprout expects the header
`Authorization: Token token=<token>` (literal `token=`, no whitespace) plus
a custom User-Agent header; this script builds both from the surrogate, so
no special placement is needed. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to
www.buzzsprout.com.

Podcast id is part of the API path, so every command takes --podcast-id.
All URLs end in `.json`; POST/PUT send
`Content-Type: application/json; charset=utf-8` or Buzzsprout 415s.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.buzzsprout"
ALLOWED_HOSTS = ("www.buzzsprout.com",)
USER_AGENT = "muse-connectors/1.0 (buzzsprout)"


try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        dynamic_credential_entry,
        ensure_allowed_url,
        read_json_response,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def get_surrogate() -> str:
    try:
        entry = dynamic_credential_entry(CREDENTIAL_NAME)
    except DynamicCredentialError:
        sys.exit(
            f"not connected: no `{CREDENTIAL_NAME}` credential is stored.\n"
            "Connect it with the secure credential flow (see this skill's "
            "Auth section for where to find your Buzzsprout API token), then retry."
        )
    return str(entry["surrogate"]).strip()


def call(podcast_id: str, method: str, path: str, payload: dict | None = None) -> dict:
    url = f"https://www.buzzsprout.com/api/{podcast_id}{path}"
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    # Literal `token=`, no whitespace (Buzzsprout rejects other shapes).
    req.add_header("Authorization", f"Token token={get_surrogate()}")
    req.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            err = body.get("error") or body
            msg = json.dumps(err) if isinstance(err, (dict, list)) else str(err)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: buzzsprout returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def summarize_episode(e: dict) -> dict:
    return {
        "id": e.get("id"),
        "title": e.get("title"),
        "description": (e.get("description") or "")[:160],
        "published_at": e.get("published_at"),
        "duration": e.get("duration"),
        "audio_url": e.get("audio_url"),
    }


def cmd_auth(args):
    result = call(args.podcast_id, "GET", "/episodes.json")
    items = result if isinstance(result, list) else result.get("episodes", [])
    print(json.dumps({"ok": True, "episodes": len(items)}, indent=2))


def cmd_episodes(args):
    result = call(args.podcast_id, "GET", "/episodes.json")
    items = result if isinstance(result, list) else result.get("episodes", [])
    print(json.dumps([summarize_episode(e) for e in items], indent=2))


def cmd_episode_get(args):
    result = call(args.podcast_id, "GET", f"/episodes/{args.episode_id}.json")
    ep = result.get("episode", result)
    print(json.dumps(summarize_episode(ep), indent=2))


def episode_payload(args) -> dict:
    try:
        return json.loads(args.payload)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --payload is not valid JSON: {exc}")


def cmd_episode_create(args):
    result = call(args.podcast_id, "POST", "/episodes.json", episode_payload(args))
    ep = result.get("episode", result)
    print(json.dumps(summarize_episode(ep), indent=2))


def cmd_episode_update(args):
    result = call(args.podcast_id, "PUT", f"/episodes/{args.episode_id}.json",
                  episode_payload(args))
    ep = result.get("episode", result)
    print(json.dumps(summarize_episode(ep), indent=2))


def cmd_episode_delete(args):
    call(args.podcast_id, "DELETE", f"/episodes/{args.episode_id}.json")
    print(json.dumps({"ok": True, "deleted": args.episode_id}, indent=2))


def cmd_players(args):
    result = call(args.podcast_id, "GET", "/players.json")
    items = result if isinstance(result, list) else result.get("players", [])
    print(json.dumps(items, indent=2))


def add_podcast_id(p):
    p.add_argument("--podcast-id", required=True,
                   help="Buzzsprout podcast id (part of the API path)")


def main():
    parser = argparse.ArgumentParser(description="Buzzsprout API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API token (lists episodes)")
    add_podcast_id(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("episodes", help="list episodes")
    add_podcast_id(p)
    p.set_defaults(func=cmd_episodes)

    p = sub.add_parser("episode-get", help="get one episode")
    add_podcast_id(p)
    p.add_argument("--episode-id", required=True)
    p.set_defaults(func=cmd_episode_get)

    p = sub.add_parser("episode-create", help="create an episode (confirm first)")
    add_podcast_id(p)
    p.add_argument("--payload", required=True,
                   help='JSON episode object, e.g. \'{"title":"Ep 12","description":"...","audio_url":"https://..."}\'')
    p.set_defaults(func=cmd_episode_create)

    p = sub.add_parser("episode-update", help="update an episode (confirm first)")
    add_podcast_id(p)
    p.add_argument("--episode-id", required=True)
    p.add_argument("--payload", required=True, help="JSON with the fields to update")
    p.set_defaults(func=cmd_episode_update)

    p = sub.add_parser("episode-delete", help="delete an episode (confirm first)")
    add_podcast_id(p)
    p.add_argument("--episode-id", required=True)
    p.set_defaults(func=cmd_episode_delete)

    p = sub.add_parser("players", help="list embed players")
    add_podcast_id(p)
    p.set_defaults(func=cmd_players)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
