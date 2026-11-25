#!/usr/bin/env python3
"""Minimal ElevenLabs API CLI for the muse-connectors ElevenLabs skill.

Auth: loads the per-user `custom.elevenlabs` credential as a surrogate via
the bundled dynamic_credentials helper. The real key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.elevenlabs.io. The key travels as the `xi-api-key` header.

COST WARNING: text-to-speech consumes characters from the account's quota,
which costs real money on paid plans. Every `text-to-speech` call requires
an exact --confirm string naming the voice and character count, on every
call. Confirm with the user before every generation.
HONESTY NOTE: the TTS endpoint path and request body below are taken from
ElevenLabs' public API docs and have not yet been verified in a live flow.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.elevenlabs"
ALLOWED_HOSTS = ("api.elevenlabs.io",)
API = "https://api.elevenlabs.io/v1"
CONNECT_GUIDANCE = (
    "not connected: approve ElevenLabs access via the secure credential flow "
    "(credentials.request_api_access) as `custom.elevenlabs` (create an API "
    "key at elevenlabs.io/app/settings/api-keys), then retry."
)
DEFAULT_MODEL = "eleven_multilingual_v2"  # documented default TTS model

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


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def _authed_req(url: str, data: bytes | None = None,
                headers: dict | None = None, method: str | None = None):
    req = urllib.request.Request(url, data=data, headers=headers or {},
                                 method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        if "missing" in str(exc) or "surrogate" in str(exc):
            sys.exit(CONNECT_GUIDANCE)
        sys.exit(f"error: credential problem: {exc}")
    return req


def _detail(exc) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
        detail = json.loads(body).get("detail", {}).get("message", body)
    except Exception:
        detail = str(exc)
    return detail


def call(path: str) -> dict:
    """GET a JSON endpoint."""
    req = _authed_req(API + path)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: elevenlabs returned HTTP {exc.code}: {_detail(exc)}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def call_raw(path: str, payload: dict) -> bytes:
    """POST a JSON payload and return the raw (binary) response body."""
    data = json.dumps(payload).encode("utf-8")
    req = _authed_req(API + path, data=data,
                      headers={"Content-Type": "application/json",
                               "Accept": "audio/mpeg"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: elevenlabs returned HTTP {exc.code}: {_detail(exc)}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_me(_args):
    result = call("/user")
    sub = result.get("subscription") or {}
    print(json.dumps(
        {"tier": sub.get("tier"), "character_count": sub.get("character_count"),
         "character_limit": sub.get("character_limit")},
        indent=2))


def cmd_voices(_args):
    result = call("/voices")
    voices = [
        {"voice_id": v.get("voice_id"), "name": v.get("name"),
         "category": v.get("category")}
        for v in result.get("voices", [])
    ]
    print(json.dumps(voices, indent=2))


def resolve_voice(args) -> tuple[str, str]:
    """Return (voice_id, voice_name) from --voice-id or --voice-name."""
    if args.voice_id:
        return args.voice_id, args.voice_id
    if not args.voice_name:
        sys.exit("error: pass --voice-id or --voice-name")
    result = call("/voices")
    matches = [v for v in result.get("voices", [])
               if (v.get("name") or "").lower() == args.voice_name.lower()]
    if not matches:
        names = [v.get("name") for v in result.get("voices", [])]
        sys.exit(f"error: no voice named {args.voice_name!r}; run `voices` "
                 f"for the list ({', '.join(names[:10])})")
    if len(matches) > 1:
        ids = [m.get("voice_id") for m in matches]
        sys.exit(f"error: {len(matches)} voices match {args.voice_name!r}; "
                 f"pass --voice-id instead ({', '.join(ids)})")
    return matches[0].get("voice_id"), matches[0].get("name")


def cmd_text_to_speech(args):
    voice_id, voice_name = resolve_voice(args)
    chars = len(args.text)
    voice_settings = {}
    if args.voice_settings:
        try:
            voice_settings = json.loads(args.voice_settings)
        except json.JSONDecodeError as exc:
            sys.exit(f"error: --voice-settings is not valid JSON: {exc}")
        if not isinstance(voice_settings, dict):
            sys.exit("error: --voice-settings must be a JSON object")
    expected = f'tts {chars} chars with voice "{voice_name}"'
    need_confirm(
        args, expected,
        f"generating speech from {chars} characters with ElevenLabs voice "
        f'"{voice_name}" ({voice_id}), model {args.model_id} — this consumes '
        "characters from the account quota (real money on paid plans).")
    payload = {"text": args.text, "model_id": args.model_id}
    if voice_settings:
        payload["voice_settings"] = voice_settings
    audio = call_raw(f"/text-to-speech/{voice_id}", payload)
    with open(args.out, "wb") as fh:
        fh.write(audio)
    print(json.dumps({"ok": True, "saved": args.out,
                      "voice": voice_name, "characters": chars,
                      "model": args.model_id,
                      "bytes": len(audio)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="ElevenLabs API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("me", help="subscription tier and character usage")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("voices", help="list available voices")
    p.set_defaults(func=cmd_voices)

    p = sub.add_parser("text-to-speech",
                       help="generate speech from text (needs --confirm; spends quota)")
    p.add_argument("--text", required=True)
    p.add_argument("--voice-id", default=None,
                   help="voice id (wins over --voice-name)")
    p.add_argument("--voice-name", default=None,
                   help="voice name, resolved via the voices list")
    p.add_argument("--out", required=True, help="output audio file path")
    p.add_argument("--model-id", default=DEFAULT_MODEL)
    p.add_argument("--voice-settings", default=None,
                   help='JSON object of voice settings, e.g. \'{"stability":0.5,"similarity_boost":0.75}\'')
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_text_to_speech)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
