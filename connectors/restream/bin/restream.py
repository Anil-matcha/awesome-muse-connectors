#!/usr/bin/env python3
"""Minimal Restream API CLI for the muse-connectors restream skill.

Auth: loads the per-user `custom.restream` credential as a surrogate via
the bundled dynamic_credentials helper. Restream uses OAuth 2.0
(authorization-code); the token is collected through the secure credential
flow (`credentials.request_api_access`) and travels as
`Authorization: Bearer <access_token>`. The real token never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.restream.io.

Live chat is a real-time WebSocket (wss://chat.api.restream.io/ws) and is
out of scope for this CLI; it is documented in the skill only.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.restream"
ALLOWED_HOSTS = ("api.restream.io",)
API = "https://api.restream.io/v2"

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


def call(method: str, path: str, payload: dict | None = None) -> dict:
    url = API + path
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
        sys.exit(f"error: restream returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def summarize_channel(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "name": c.get("name") or c.get("displayName"),
        "service": c.get("service") or c.get("channelIdentifier"),
        "active": c.get("active"),
    }


def cmd_auth(_args):
    result = call("GET", "/user/profile")
    print(json.dumps({"ok": True,
                      "username": result.get("username"),
                      "email": result.get("email")}, indent=2))


def cmd_profile(_args):
    print(json.dumps(call("GET", "/user/profile"), indent=2))


def cmd_channels(_args):
    result = call("GET", "/user/channel/all")
    channels = result if isinstance(result, list) else result.get("channels", result.get("data", []))
    print(json.dumps([summarize_channel(c) for c in channels], indent=2))


def json_payload(raw: str) -> dict:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --payload is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        sys.exit("error: --payload must be a JSON object")
    return payload


def cmd_channel_update(args):
    result = call("PATCH", f"/user/channel/{args.id}", json_payload(args.payload))
    print(json.dumps(summarize_channel(result if isinstance(result, dict) else {}), indent=2))


def cmd_channel_meta_get(args):
    print(json.dumps(call("GET", f"/user/channel-meta/{args.id}"), indent=2))


def cmd_channel_meta_update(args):
    result = call("PATCH", f"/user/channel-meta/{args.id}", json_payload(args.payload))
    print(json.dumps(result, indent=2))


def cmd_stream_key(_args):
    result = call("GET", "/user/streamKey")
    print("warning: output contains your live stream key; treat it as a "
          "secret and never paste it into chat, logs, or tickets.",
          file=sys.stderr)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Restream API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the OAuth token (reads your profile)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("profile", help="show your Restream profile")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("channels", help="list streaming destinations (channels)")
    p.set_defaults(func=cmd_channels)

    p = sub.add_parser("channel-update",
                       help="PATCH a channel, e.g. toggle a destination (confirm first)")
    p.add_argument("--id", required=True, help="channel id")
    p.add_argument("--payload", required=True,
                   help='JSON patch body, e.g. \'{"active": false}\'')
    p.set_defaults(func=cmd_channel_update)

    p = sub.add_parser("channel-meta-get", help="get a channel's metadata")
    p.add_argument("--id", required=True, help="channel id")
    p.set_defaults(func=cmd_channel_meta_get)

    p = sub.add_parser("channel-meta-update",
                       help="PATCH a channel's metadata (confirm first)")
    p.add_argument("--id", required=True, help="channel id")
    p.add_argument("--payload", required=True, help="JSON patch body")
    p.set_defaults(func=cmd_channel_meta_update)

    p = sub.add_parser("stream-key", help="show your stream key (output is a live secret)")
    p.set_defaults(func=cmd_stream_key)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
