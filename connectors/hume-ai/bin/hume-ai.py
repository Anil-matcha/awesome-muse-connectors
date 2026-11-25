#!/usr/bin/env python3
"""Minimal Hume AI API CLI for the muse-connectors hume-ai skill.

Auth: loads the per-user `custom.hume-ai` credential as a surrogate via the
bundled dynamic_credentials helper. The real key never touches this script:
the runtime swaps the surrogate on approved egress, only to api.hume.ai.
REST auth uses the `X-HUME-API-KEY` header (never Bearer).

Scope: Octave TTS (REST) plus EVI config list/get. Live EVI sessions are
real-time WebSockets and are out of CLI scope. EVI config changes and cloned
voices are confirmation-gated (see SKILL.md) and are not in this draft CLI.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.hume-ai"
ALLOWED_HOSTS = ("api.hume.ai",)
API = "https://api.hume.ai"

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
    """Call the Hume API. raw=True returns (bytes, content_type)."""
    url = API + path
    data = None
    headers = {}
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
            msg = body.get("fault", {}).get("faultstring", str(exc)) \
                if isinstance(body.get("fault"), dict) else body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: hume returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def _no_credential_exit():
    print(json.dumps({
        "ok": False,
        "error": "no credential stored for custom.hume-ai",
        "connect": ("store a Hume API key as custom.hume-ai via the secure "
                    "credential flow (credentials.request_api_access), then rerun auth"),
    }, indent=2))
    sys.exit(1)


def cmd_auth(_args):
    try:
        result = call("GET", "/v0/evi/configs")
    except DynamicCredentialError:
        _no_credential_exit()
    except Exception as exc:  # authd unavailable or network down: no traceback
        print(json.dumps({"ok": False, "error": f"status check failed: {exc}"},
                         indent=2))
        sys.exit(1)
    configs = result.get("configs_page") or result.get("configs") or result
    count = len(configs) if isinstance(configs, list) else None
    print(json.dumps({"ok": True, "configs": count}, indent=2))


def _config_items(result):
    configs = result.get("configs_page") or result.get("configs") or result
    return configs if isinstance(configs, list) else []


def cmd_configs(_args):
    result = call("GET", "/v0/evi/configs")
    configs = [{"id": c.get("id"), "name": c.get("name"),
                "version": c.get("version")} for c in _config_items(result)]
    print(json.dumps(configs, indent=2))


def cmd_config_get(args):
    result = call("GET", f"/v0/evi/configs/{args.id}")
    print(json.dumps(result, indent=2))


def _extract_audio(result):
    """Best-effort base64 audio extraction from an Octave TTS JSON response."""
    gens = result.get("generations") or []
    if not gens:
        return None
    gen = gens[0]
    for key in ("audio", "audio_base64", "audio_data"):
        val = gen.get(key)
        if isinstance(val, str) and len(val) > 100:
            try:
                return base64.b64decode(val)
            except Exception:
                continue
    return None


def cmd_tts(args):
    utterance = {"text": args.text}
    if args.voice:
        utterance["voice"] = {"name": args.voice, "provider": "HUME_AI"}
    if args.description:
        utterance["description"] = args.description
    payload = {"utterances": [utterance], "format": {"type": "mp3"}}
    body, ctype = call("POST", "/v0/tts", payload=payload, raw=True)
    audio = None
    if ctype and ctype.startswith("audio"):
        audio = body
    else:
        try:
            result = json.loads(body.decode("utf-8"))
        except Exception:
            result = {}
        audio = _extract_audio(result)
        if audio is None:
            print(json.dumps({
                "ok": False,
                "note": ("audio could not be extracted from the TTS response; "
                         "raw provider response follows"),
                "response": result,
            }, indent=2))
            sys.exit(1)
    with open(args.out, "wb") as fh:
        fh.write(audio)
    print(json.dumps({"ok": True, "path": args.out, "bytes": len(audio)},
                     indent=2))


def main():
    parser = argparse.ArgumentParser(description="Hume AI API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="status check: list EVI configs and confirm the key works")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("configs", help="list EVI configs")
    p.set_defaults(func=cmd_configs)

    p = sub.add_parser("config-get", help="details for a single EVI config")
    p.add_argument("--id", required=True, help="EVI config id")
    p.set_defaults(func=cmd_config_get)

    p = sub.add_parser("tts", help="synthesize text with Octave TTS (credit-metered)")
    p.add_argument("--text", required=True, help="text to synthesize")
    p.add_argument("--voice", default=None,
                   help="Octave voice name, e.g. 'Ava Song' (optional)")
    p.add_argument("--description", default=None,
                   help="acting instructions for the voice (optional)")
    p.add_argument("--out", default="hume-output.mp3",
                   help="local path for the audio file (default: hume-output.mp3)")
    p.set_defaults(func=cmd_tts)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
