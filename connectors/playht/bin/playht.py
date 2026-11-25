#!/usr/bin/env python3
"""Minimal PlayHT TTS API CLI for the muse-connectors playht skill.

Auth: loads the per-user `custom.playht` credential as a surrogate via the
bundled dynamic_credentials helper. The real key never touches this script:
the runtime swaps the surrogate on approved egress, only to api.play.ht.
PlayHT's current API uses a single uppercase `AUTHORIZATION: Bearer <key>`
header (older dual-header docs are stale); the stored credential value must
include the `Bearer ` prefix, since the helper places the header value
verbatim.

Audio outputs: TTS returns audio binary; the CLI saves it to a local path
(--out) and prints that path. Voice cloning and batch synthesis are
confirmation-gated (see SKILL.md).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.playht"
ALLOWED_HOSTS = ("api.play.ht",)
API = "https://api.play.ht"
MAX_CHARS = 20000

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


def call(method: str, path: str, payload: dict | None = None, raw: bool = False):
    """Call the PlayHT API. raw=True returns (bytes, content_type)."""
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            if raw:
                return resp.read(), resp.headers.get_content_type()
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error_message", body.get("error", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: playht returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def _no_credential_exit():
    print(json.dumps({
        "ok": False,
        "error": "no credential stored for custom.playht",
        "connect": ("store a PlayHT API key as custom.playht via the secure "
                    "credential flow (credentials.request_api_access), with the "
                    "stored value including the 'Bearer ' prefix, then rerun auth"),
    }, indent=2))
    sys.exit(1)


def cmd_auth(_args):
    try:
        result = call("GET", "/api/v2/voices")
    except DynamicCredentialError:
        _no_credential_exit()
    except Exception as exc:  # authd unavailable or network down: no traceback
        print(json.dumps({"ok": False, "error": f"status check failed: {exc}"},
                         indent=2))
        sys.exit(1)
    voices = result if isinstance(result, list) else result.get("voices", [])
    count = len(voices) if isinstance(voices, list) else None
    print(json.dumps({"ok": True, "voices": count}, indent=2))


def _voice_items(result):
    if isinstance(result, list):
        return result
    voices = result.get("voices", result)
    return voices if isinstance(voices, list) else []


def cmd_voices(_args):
    result = call("GET", "/api/v2/voices")
    voices = [{"id": v.get("id"), "name": v.get("name"),
               "language": v.get("language"), "gender": v.get("gender")}
              for v in _voice_items(result)]
    print(json.dumps(voices, indent=2))


def cmd_clones(_args):
    result = call("GET", "/api/v2/cloned-voices")
    clones = result if isinstance(result, list) else result.get("voices", result)
    print(json.dumps(clones, indent=2))


def cmd_tts(args):
    if len(args.text) > MAX_CHARS:
        sys.exit(f"error: text is {len(args.text)} chars; PlayHT caps a "
                 f"request at {MAX_CHARS} chars. Split the script and retry.")
    payload = {"text": args.text, "voice": args.voice_id,
               "output_format": "mp3", "quality": "high"}
    audio, _ctype = call("POST", "/api/v2/tts/stream", payload=payload, raw=True)
    with open(args.out, "wb") as fh:
        fh.write(audio)
    print(json.dumps({"ok": True, "path": args.out, "bytes": len(audio)},
                     indent=2))


def cmd_clone(args):
    try:
        with open(args.json, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"error: cannot read clone body from {args.json}: {exc}")
    result = call("POST", "/api/v2/cloned-voices/instant/", payload=payload)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="PlayHT TTS API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="status check: list voices and confirm the key works")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("voices", help="list stock voices")
    p.set_defaults(func=cmd_voices)

    p = sub.add_parser("clones", help="list your cloned voices")
    p.set_defaults(func=cmd_clones)

    p = sub.add_parser("tts", help="streaming synthesis to an audio file (credit-metered, max 20k chars)")
    p.add_argument("--text", required=True, help="text to synthesize")
    p.add_argument("--voice-id", required=True, help="voice id (see voices or clones)")
    p.add_argument("--out", default="playht-output.mp3",
                   help="local path for the audio file (default: playht-output.mp3)")
    p.set_defaults(func=cmd_tts)

    p = sub.add_parser("clone", help="create an instant voice clone (CONFIRMATION-GATED)")
    p.add_argument("--json", required=True,
                   help="path to a JSON file with the clone request body, per current PlayHT docs")
    p.set_defaults(func=cmd_clone)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
