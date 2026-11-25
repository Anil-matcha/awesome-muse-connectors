#!/usr/bin/env python3
"""Minimal Podbean API CLI for the muse-connectors podbean skill.

Auth: loads the per-user `custom.podbean` credential as a surrogate via
the bundled dynamic_credentials helper. Podbean uses OAuth 2.0; the token
is collected through the secure credential flow (`credentials.request_api_access`)
and travels as `Authorization: Bearer <access_token>`. The real token never
touches this script: the runtime swaps the surrogate on approved egress,
only to api.podbean.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.podbean"
ALLOWED_HOSTS = ("api.podbean.com",)
API = "https://api.podbean.com/v1"

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
            "Connect it with the secure credential flow (provider OAuth, see "
            "this skill's Auth section), then retry."
        )
    return str(entry["surrogate"]).strip()


def call(method: str, path: str, payload: dict | None = None,
         params: dict | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    req.add_header("Authorization", f"Bearer {get_surrogate()}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            err = body.get("error") or body.get("message") or body
            msg = json.dumps(err) if isinstance(err, (dict, list)) else str(err)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: podbean returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def summarize_podcast(p: dict) -> dict:
    return {
        "id": p.get("id") or p.get("podcast_id"),
        "title": p.get("title"),
        "description": (p.get("desc") or p.get("description") or "")[:160],
    }


def summarize_episode(e: dict) -> dict:
    return {
        "id": e.get("id") or e.get("episode_id"),
        "title": e.get("title"),
        "status": e.get("status"),
        "publish_time": e.get("publish_time"),
        "duration": e.get("duration"),
        "audio_url": e.get("audio_url") or e.get("media_url"),
    }


def pluck_list(result: dict, *keys) -> list:
    for key in keys:
        val = result.get(key)
        if isinstance(val, list):
            return val
    return []


def cmd_auth(_args):
    result = call("GET", "/podcasts")
    podcasts = pluck_list(result, "podcasts", "data")
    print(json.dumps({"ok": True, "podcasts": len(podcasts)}, indent=2))


def cmd_podcasts(_args):
    result = call("GET", "/podcasts")
    print(json.dumps([summarize_podcast(p) for p in pluck_list(result, "podcasts", "data")],
                     indent=2))


def cmd_episodes(args):
    result = call("GET", f"/podcasts/{args.podcast_id}/episodes",
                  params={"limit": args.limit})
    print(json.dumps([summarize_episode(e) for e in pluck_list(result, "episodes", "data")],
                     indent=2))


def episode_payload(args) -> dict:
    try:
        return json.loads(args.payload)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --payload is not valid JSON: {exc}")


def cmd_episode_create(args):
    result = call("POST", "/episodes", episode_payload(args))
    ep = result.get("episode", result)
    print(json.dumps(summarize_episode(ep), indent=2))


def cmd_episode_update(args):
    result = call("PUT", f"/episodes/{args.episode_id}", episode_payload(args))
    ep = result.get("episode", result)
    print(json.dumps(summarize_episode(ep), indent=2))


def cmd_episode_delete(args):
    call("DELETE", f"/episodes/{args.episode_id}")
    print(json.dumps({"ok": True, "deleted": args.episode_id}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Podbean API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the OAuth token (lists podcasts)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("podcasts", help="list podcasts on the account")
    p.set_defaults(func=cmd_podcasts)

    p = sub.add_parser("episodes", help="list episodes of a podcast")
    p.add_argument("--podcast-id", required=True)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_episodes)

    p = sub.add_parser("episode-create", help="create an episode (confirm first)")
    p.add_argument("--payload", required=True,
                   help='JSON episode object per Podbean API docs, e.g. \'{"title":"Ep 12", ...}\'')
    p.set_defaults(func=cmd_episode_create)

    p = sub.add_parser("episode-update", help="update an episode (confirm first)")
    p.add_argument("--episode-id", required=True)
    p.add_argument("--payload", required=True, help="JSON with the fields to update")
    p.set_defaults(func=cmd_episode_update)

    p = sub.add_parser("episode-delete", help="delete an episode (confirm first)")
    p.add_argument("--episode-id", required=True)
    p.set_defaults(func=cmd_episode_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
