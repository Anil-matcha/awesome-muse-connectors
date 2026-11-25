#!/usr/bin/env python3
"""Minimal Transistor.fm API CLI for the muse-connectors transistor skill.

Auth: loads the per-user `custom.transistor` credential as a surrogate via
the bundled dynamic_credentials helper. Transistor expects the raw key in
the `x-api-key` header (no Bearer prefix); this script builds that header
from the surrogate itself, so no special placement is needed. The real key
never touches this script: the runtime swaps the surrogate on approved
egress, only to api.transistor.fm.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.transistor"
ALLOWED_HOSTS = ("api.transistor.fm",)
API = "https://api.transistor.fm/v1"

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
            "Auth section for where to create a Transistor API key), then retry."
        )
    return str(entry["surrogate"]).strip()


def call(method: str, path: str, payload: dict | None = None) -> dict:
    url = API + path
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    req.add_header("x-api-key", get_surrogate())
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            err = body.get("errors") or body.get("error") or body
            msg = json.dumps(err) if isinstance(err, (dict, list)) else str(err)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: transistor returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def summarize_show(s: dict) -> dict:
    a = s.get("attributes", {}) if isinstance(s, dict) else {}
    return {"id": s.get("id"), "title": a.get("title"), "description": (a.get("description") or "")[:120]}


def summarize_episode(e: dict) -> dict:
    a = e.get("attributes", {}) if isinstance(e, dict) else {}
    return {
        "id": e.get("id"),
        "title": a.get("title"),
        "status": a.get("status"),
        "published_at": a.get("published_at"),
        "duration": a.get("duration"),
        "audio_url": a.get("audio_url") or a.get("media_url"),
    }


def cmd_auth(_args):
    result = call("GET", "/shows")
    data = result.get("data", [])
    print(json.dumps({"ok": True, "shows": len(data)}, indent=2))


def cmd_shows(_args):
    result = call("GET", "/shows")
    print(json.dumps([summarize_show(s) for s in result.get("data", [])], indent=2))


def cmd_episodes(args):
    result = call("GET", f"/shows/{args.show_id}/episodes")
    print(json.dumps([summarize_episode(e) for e in result.get("data", [])], indent=2))


def cmd_episode_create(args):
    payload = {
        "data": {
            "type": "episodes",
            "attributes": {
                "show_id": args.show_id,
                "title": args.title,
                "audio_url": args.audio_url,
            },
        }
    }
    if args.description:
        payload["data"]["attributes"]["description"] = args.description
    result = call("POST", "/episodes", payload)
    print(json.dumps(summarize_episode(result.get("data", {})), indent=2))


def cmd_episode_update(args):
    attributes = {}
    if args.title:
        attributes["title"] = args.title
    if args.description:
        attributes["description"] = args.description
    if not attributes:
        sys.exit("error: nothing to update; pass --title and/or --description")
    result = call("PATCH", f"/episodes/{args.id}",
                  {"data": {"type": "episodes", "id": args.id, "attributes": attributes}})
    print(json.dumps(summarize_episode(result.get("data", {})), indent=2))


def cmd_episode_delete(args):
    call("DELETE", f"/episodes/{args.id}")
    print(json.dumps({"ok": True, "deleted": args.id}, indent=2))


def cmd_authorize_upload(_args):
    # Step 1 of the two-step upload: returns upload target details.
    result = call("GET", "/episodes/authorize_upload")
    print(json.dumps(result, indent=2))


def find_upload_target(result: dict) -> tuple[str, str | None]:
    """Best-effort extraction of (upload_url, audio_url) from the authorize
    response. Field names are not pinned in the public docs this connector
    was written from, so this checks the common shapes and bails out with
    the raw response rather than guessing."""
    data = result.get("data")
    attrs = data.get("attributes", {}) if isinstance(data, dict) else {}

    def first(*keys):
        for key in keys:
            for scope in (attrs, result):
                val = scope.get(key)
                if isinstance(val, str) and val.startswith("http"):
                    return val
        return None

    upload_url = first("upload_url", "put_url", "url")
    if not upload_url:
        print(json.dumps(result, indent=2))
        sys.exit(
            "error: could not find an upload URL in the authorize_upload "
            "response (printed above). PUT your audio file to the provider's "
            "upload target, then run `episode-create --audio-url <url>`."
        )
    audio_url = first("audio_url", "media_url")
    return upload_url, audio_url


def cmd_upload(args):
    # Two-step upload: authorize -> PUT file bytes -> create draft episode.
    auth_result = call("GET", "/episodes/authorize_upload")
    upload_url, audio_url = find_upload_target(auth_result)
    ensure_allowed_url(upload_url, allowed_hosts=ALLOWED_HOSTS)

    with open(args.file, "rb") as fh:
        file_bytes = fh.read()
    content_type = mimetypes.guess_type(args.file)[0] or "audio/mpeg"
    req = urllib.request.Request(upload_url, data=file_bytes, method="PUT",
                                 headers={"Content-Type": content_type,
                                          "Content-Length": str(len(file_bytes))})
    try:
        with urllib.request.urlopen(req, timeout=300):
            pass
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: upload PUT failed with HTTP {exc.code}: {exc.read()[:500]!r}")
    except Exception as exc:
        sys.exit(f"error: upload PUT failed: {exc}")

    if not audio_url:
        print(json.dumps({"ok": True, "uploaded": True, "upload_url": upload_url}, indent=2))
        sys.exit(
            "uploaded, but the audio URL for the episode was not identifiable "
            "in the authorize response. Find the file's public URL and run "
            "`episode-create --audio-url <url>`."
        )
    result = call("POST", "/episodes", {
        "data": {"type": "episodes", "attributes": {
            "show_id": args.show_id, "title": args.title, "audio_url": audio_url,
        }}
    })
    print(json.dumps({"ok": True, "uploaded": True,
                      "episode": summarize_episode(result.get("data", {}))}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Transistor.fm API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key (lists shows)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("shows", help="list your shows")
    p.set_defaults(func=cmd_shows)

    p = sub.add_parser("episodes", help="list episodes of a show")
    p.add_argument("--show-id", required=True, help="Transistor show id")
    p.set_defaults(func=cmd_episodes)

    p = sub.add_parser("episode-create", help="create a draft episode (confirm first)")
    p.add_argument("--show-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--audio-url", required=True, help="public URL of the episode audio")
    p.add_argument("--description")
    p.set_defaults(func=cmd_episode_create)

    p = sub.add_parser("episode-update", help="update an episode (confirm first)")
    p.add_argument("--id", required=True, help="episode id")
    p.add_argument("--title")
    p.add_argument("--description")
    p.set_defaults(func=cmd_episode_update)

    p = sub.add_parser("episode-delete", help="delete an episode (confirm first)")
    p.add_argument("--id", required=True, help="episode id")
    p.set_defaults(func=cmd_episode_delete)

    p = sub.add_parser("authorize-upload", help="step 1 of audio upload: get upload target (prints raw JSON)")
    p.set_defaults(func=cmd_authorize_upload)

    p = sub.add_parser("upload", help="two-step audio upload + draft episode (confirm first: consumes storage)")
    p.add_argument("--file", required=True, help="local audio file to upload")
    p.add_argument("--show-id", required=True)
    p.add_argument("--title", required=True)
    p.set_defaults(func=cmd_upload)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
