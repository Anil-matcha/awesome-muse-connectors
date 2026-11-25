#!/usr/bin/env python3
"""Minimal Deepgram API CLI for the muse-connectors deepgram skill.

Auth: loads the per-user `custom.deepgram` credential as a surrogate via the
bundled dynamic_credentials helper. The real key never touches this script:
the runtime swaps the surrogate on approved egress, only to api.deepgram.com.
Deepgram uses exactly `Authorization: Token <api_key>` (NOT Bearer); the
stored credential value must include the `Token ` prefix, since the helper
places the header value verbatim.

Audio in: transcribe takes a local file path, uploads the bytes to
POST /v1/listen, and prints the transcript JSON. Audio out: tts saves
synthesized audio to a local path and prints it.

Key and project management are confirmation-gated (see SKILL.md) and are not
in this draft CLI. Live WebSocket STT is out of CLI scope.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.deepgram"
ALLOWED_HOSTS = ("api.deepgram.com",)
API = "https://api.deepgram.com"
TTS_CHAR_LIMIT = 2000

CONTENT_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
    ".webm": "audio/webm",
}

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


def _request(method: str, path: str, data: bytes | None = None,
             content_type: str | None = None, raw: bool = False):
    url = API + path
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            if raw:
                return resp.read(), resp.headers.get_content_type()
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            err = body.get("err_msg") or body.get("error") or str(exc)
        except Exception:
            err = str(exc)
        sys.exit(f"error: deepgram returned HTTP {exc.code}: {err}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def _no_credential_exit():
    print(json.dumps({
        "ok": False,
        "error": "no credential stored for custom.deepgram",
        "connect": ("store a Deepgram API key as custom.deepgram via the secure "
                    "credential flow (credentials.request_api_access), with the "
                    "stored value exactly 'Token <api_key>', then rerun auth"),
    }, indent=2))
    sys.exit(1)


def cmd_auth(_args):
    try:
        result = _request("GET", "/v1/projects")
    except DynamicCredentialError:
        _no_credential_exit()
    except Exception as exc:  # authd unavailable or network down: no traceback
        print(json.dumps({"ok": False, "error": f"status check failed: {exc}"},
                         indent=2))
        sys.exit(1)
    projects = result.get("projects", result)
    count = len(projects) if isinstance(projects, list) else None
    print(json.dumps({"ok": True, "projects": count}, indent=2))


def cmd_projects(_args):
    result = _request("GET", "/v1/projects")
    projects = result.get("projects", result)
    if not isinstance(projects, list):
        print(json.dumps(result, indent=2))
        return
    print(json.dumps([{"id": p.get("project_id"), "name": p.get("name")}
                      for p in projects], indent=2))


def _content_type_for(path: str) -> str:
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return CONTENT_TYPES.get(ext, "audio/wav")


def cmd_transcribe(args):
    try:
        with open(args.file, "rb") as fh:
            audio = fh.read()
    except OSError as exc:
        sys.exit(f"error: cannot read audio file {args.file}: {exc}")
    params = {"model": args.model}
    if args.diarize:
        params["diarize"] = "true"
    if args.summarize:
        params["summarize"] = "true"
    if args.topics:
        params["topics"] = "true"
    if args.sentiment:
        params["sentiment"] = "true"
    path = "/v1/listen?" + urllib.parse.urlencode(params)
    result = _request("POST", path, data=audio,
                      content_type=_content_type_for(args.file))
    print(json.dumps(result, indent=2))


def cmd_tts(args):
    if len(args.text) > TTS_CHAR_LIMIT:
        sys.exit(f"error: text is {len(args.text)} chars; Deepgram TTS caps a "
                 f"request at {TTS_CHAR_LIMIT} chars. Split the text and retry.")
    params = urllib.parse.urlencode({"model": args.model, "encoding": "mp3"})
    body = json.dumps({"text": args.text}).encode("utf-8")
    audio, _ctype = _request("POST", "/v1/speak?" + params, data=body,
                             content_type="application/json", raw=True)
    with open(args.out, "wb") as fh:
        fh.write(audio)
    print(json.dumps({"ok": True, "path": args.out, "bytes": len(audio)},
                     indent=2))


def main():
    parser = argparse.ArgumentParser(description="Deepgram API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="status check: list projects and confirm the key works")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("projects", help="list Deepgram projects")
    p.set_defaults(func=cmd_projects)

    p = sub.add_parser("transcribe", help="transcribe a local audio file (metered by audio duration)")
    p.add_argument("--file", required=True, help="local audio file path")
    p.add_argument("--model", default="nova-3", help="STT model (default: nova-3)")
    p.add_argument("--diarize", action="store_true", help="speaker diarization")
    p.add_argument("--summarize", action="store_true", help="generate a summary")
    p.add_argument("--topics", action="store_true", help="detect topics")
    p.add_argument("--sentiment", action="store_true", help="detect sentiment")
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("tts", help="synthesize text to an audio file (max 2000 chars)")
    p.add_argument("--text", required=True, help="text to synthesize")
    p.add_argument("--model", default="aura-2-thalia-en",
                   help="Aura voice model (default: aura-2-thalia-en)")
    p.add_argument("--out", default="deepgram-output.mp3",
                   help="local path for the audio file (default: deepgram-output.mp3)")
    p.set_defaults(func=cmd_tts)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
