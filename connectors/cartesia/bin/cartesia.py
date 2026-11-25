#!/usr/bin/env python3
"""Minimal Cartesia TTS API CLI for the muse-connectors Cartesia skill.

Auth: loads the per-user `custom.cartesia` credential as a surrogate via the
bundled dynamic_credentials helper. The real key never touches this script:
the runtime swaps the surrogate on approved egress, only to api.cartesia.ai.
Every request carries the required `Cartesia-Version: 2026-08-14` header.

Audio outputs: TTS returns audio binary; the CLI saves it to a local path
(--out) and prints that path.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.cartesia"
ALLOWED_HOSTS = ("api.cartesia.ai",)
API = "https://api.cartesia.ai"
CARTESIA_VERSION = "2026-08-14"

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


def call(method: str, path: str, payload: dict | None = None,
         raw: bool = False):
    """Call the Cartesia API. raw=True returns (bytes, content_type)."""
    url = API + path
    data = None
    headers = {"Cartesia-Version": CARTESIA_VERSION}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if raw:
                return resp.read(), resp.headers.get_content_type()
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: cartesia returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def _no_credential_exit():
    print(json.dumps({
        "ok": False,
        "error": "no credential stored for custom.cartesia",
        "connect": ("store a Cartesia API key as custom.cartesia via the "
                    "secure credential flow (credentials.request_api_access), "
                    "then rerun auth"),
    }, indent=2))
    sys.exit(1)


def cmd_auth(_args):
    try:
        result = call("GET", "/voices")
    except DynamicCredentialError:
        _no_credential_exit()
    except Exception as exc:  # authd unavailable or network down: no traceback
        print(json.dumps({"ok": False, "error": f"status check failed: {exc}"},
                         indent=2))
        sys.exit(1)
    items = result.get("data") or result.get("voices") or result
    count = len(items) if isinstance(items, list) else None
    print(json.dumps({"ok": True, "voices": count}, indent=2))


def _voice_items(result):
    items = result.get("data") or result.get("voices") or result
    return items if isinstance(items, list) else []


def cmd_voices(_args):
    result = call("GET", "/voices")
    voices = [{"id": v.get("id"), "name": v.get("name"),
               "language": v.get("language")} for v in _voice_items(result)]
    print(json.dumps(voices, indent=2))


def cmd_voice_get(args):
    result = call("GET", f"/voices/{args.id}")
    voice = result.get("data") or result
    print(json.dumps({
        "id": voice.get("id"), "name": voice.get("name"),
        "language": voice.get("language"),
        "description": voice.get("description"),
    }, indent=2))


def cmd_tts(args):
    payload = {
        "model_id": args.model_id,
        "transcript": args.text,
        "voice": {"mode": "id", "id": args.voice_id},
        "output_format": {"container": "wav", "sample_rate": 44100},
    }
    if args.language:
        payload["language"] = args.language
    audio, _ctype = call("POST", "/tts/bytes", payload=payload, raw=True)
    with open(args.out, "wb") as fh:
        fh.write(audio)
    print(json.dumps({"ok": True, "path": args.out, "bytes": len(audio)},
                     indent=2))


def main():
    parser = argparse.ArgumentParser(description="Cartesia TTS API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="status check: list voices and confirm the key works")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("voices", help="list available voices")
    p.set_defaults(func=cmd_voices)

    p = sub.add_parser("voice-get", help="details for a single voice")
    p.add_argument("--id", required=True, help="voice id")
    p.set_defaults(func=cmd_voice_get)

    p = sub.add_parser("tts", help="synthesize text to an audio file (credit-metered)")
    p.add_argument("--text", required=True, help="text to synthesize")
    p.add_argument("--voice-id", required=True, help="voice id (see voices)")
    p.add_argument("--model-id", default="sonic-3", help="model id (default: sonic-3)")
    p.add_argument("--language", default=None, help="language code, e.g. en, fr")
    p.add_argument("--out", default="cartesia-output.wav",
                   help="local path for the audio file (default: cartesia-output.wav)")
    p.set_defaults(func=cmd_tts)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
