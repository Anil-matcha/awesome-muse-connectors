#!/usr/bin/env python3
"""Minimal HeyGen API CLI for the muse-connectors heygen skill.

Auth: loads the per-user `custom.heygen` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.heygen.com, and the CLI sends it verbatim as the `X-Api-Key` header.

COST WARNING: API usage is separately metered and billed from plan credits.
Every generation spends API balance, not plan quota.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.heygen"
ALLOWED_HOSTS = ("api.heygen.com",)
BASE = "https://api.heygen.com"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        dynamic_credential_entry,
        ensure_allowed_url,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def api_key() -> str:
    try:
        return str(dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]).strip()
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")


def call(method: str, path: str, payload: dict | None = None,
         params: dict | None = None) -> dict:
    url = BASE + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    req.add_header("X-Api-Key", api_key())
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", body.get("message", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: HeyGen returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def _parse_json_arg(extra: str | None) -> dict:
    if not extra:
        return {}
    try:
        obj = json.loads(extra)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --json is not valid JSON: {exc}")
    if not isinstance(obj, dict):
        sys.exit("error: --json must be a JSON object")
    return obj


def cmd_auth(_args):
    result = call("GET", "/v2/avatars", params={"limit": 1})
    data = result.get("data", {}) if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "avatars_visible": len(data.get("avatars", []))},
                     indent=2))


def cmd_video_agent(args):
    """One-shot prompt-to-video via the Video Agent."""
    payload = {"prompt": args.prompt}
    payload.update(_parse_json_arg(args.json))
    result = call("POST", "/v1/video_agent/generate", payload=payload)
    data = result.get("data", {}) if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "video_id": data.get("video_id"),
                      "poll": f"bin/heygen.py video-status --video-id {data.get('video_id')}"},
                     indent=2))
    print("note: renders take 2-5 minutes; poll video-status until completed.",
          file=sys.stderr)


def cmd_video_generate(args):
    """Multi-scene avatar video. Full scene spec goes in --json."""
    payload = _parse_json_arg(args.json)
    if not payload:
        sys.exit("error: --json with the video generation spec is required "
                 "(avatar_id, voice_id, script/input_text, etc. per HeyGen docs)")
    result = call("POST", "/v2/video/generate", payload=payload)
    data = result.get("data", {}) if isinstance(result, dict) else {}
    print(json.dumps({"ok": True, "video_id": data.get("video_id"),
                      "poll": f"bin/heygen.py video-status --video-id {data.get('video_id')}"},
                     indent=2))


def cmd_video_status(args):
    result = call("GET", "/v1/video_status.get", params={"video_id": args.video_id})
    data = result.get("data", {}) if isinstance(result, dict) else {}
    print(json.dumps({
        "video_id": args.video_id,
        "status": data.get("status"),
        "video_url": data.get("video_url"),
        "error": data.get("error"),
    }, indent=2))


def cmd_avatars(args):
    result = call("GET", "/v2/avatars", params={"limit": args.limit})
    data = result.get("data", {}) if isinstance(result, dict) else {}
    out = [{"avatar_id": a.get("avatar_id"), "avatar_name": a.get("avatar_name"),
            "gender": a.get("gender")}
           for a in data.get("avatars", [])]
    print(json.dumps(out, indent=2))


def cmd_voices(args):
    result = call("GET", "/v2/voices", params={"limit": args.limit})
    data = result.get("data", {}) if isinstance(result, dict) else {}
    out = [{"voice_id": v.get("voice_id"), "name": v.get("name"),
            "language": v.get("language"), "gender": v.get("gender")}
           for v in data.get("voices", [])]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="HeyGen API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key (free avatars read)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("video-agent", help="prompt-to-video one-shot (confirm first; API-billed)")
    p.add_argument("--prompt", required=True)
    p.add_argument("--json", default=None, help="extra fields as a JSON object")
    p.set_defaults(func=cmd_video_agent)

    p = sub.add_parser("video-generate", help="multi-scene avatar video (confirm first; API-billed)")
    p.add_argument("--json", required=True,
                   help="full generation spec as a JSON object (avatar_id, voice_id, script, etc.)")
    p.set_defaults(func=cmd_video_generate)

    p = sub.add_parser("video-status", help="poll a video generation")
    p.add_argument("--video-id", required=True)
    p.set_defaults(func=cmd_video_status)

    p = sub.add_parser("avatars", help="list stock avatars")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_avatars)

    p = sub.add_parser("voices", help="list voices")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_voices)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
