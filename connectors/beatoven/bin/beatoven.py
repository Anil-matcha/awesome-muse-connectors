#!/usr/bin/env python3
"""Minimal Beatoven.ai API CLI for the muse-connectors beatoven skill.

Auth: loads the per-user `custom.beatoven` credential as a surrogate via the
bundled dynamic_credentials helper. The real API token never touches this
script: the runtime swaps the surrogate on approved egress, only to
public-api.beatoven.ai (plus the download host the API itself returns), and
the CLI sends it verbatim as `Authorization: Bearer <token>`.

Endpoint paths are from Beatoven's published api-spec.md
(github.com/Beatoven/public-api, reconciled 2026-09-16):
  POST /api/v1/tracks/compose   -> {"status": "started", "task_id": ...}
  GET  /api/v1/tasks/<task_id>  -> status composing|running|composed, with
                                   track_url and stems_url (bass/chords/
                                   melody/percussion) when composed.

Beatoven output is royalty-free and Fairly Trained certified (licensed
training data): commercially safe. The only verified self-serve music API.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.beatoven"
API_HOST = "public-api.beatoven.ai"
BASE = f"https://{API_HOST}"

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


def api_token() -> str:
    try:
        return str(dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]).strip()
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")


def call_api(method: str, path: str, payload: dict | None = None) -> dict:
    url = BASE + path
    ensure_allowed_url(url, allowed_hosts=(API_HOST,))
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    req.add_header("Authorization", f"Bearer {api_token()}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("error", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: Beatoven returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def download_url(url: str, out: str) -> None:
    """Download a composed asset. The host comes from Beatoven's own task
    response (the user's own composition result); it is added to the allowed
    hosts for this single fetch alongside the API host."""
    host = urllib.parse.urlparse(url).hostname or ""
    ensure_allowed_url(url, allowed_hosts=(API_HOST, host))
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp, open(out, "wb") as fh:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                fh.write(chunk)
    except Exception as exc:
        sys.exit(f"error: download failed: {exc}")


def cmd_auth(_args):
    # No zero-cost probe in the published spec; auth verifies the credential
    # is collected and well-formed. Composing spends metered usage.
    token = api_token()
    if not token:
        sys.exit("error: empty credential")
    print(json.dumps({"ok": True, "base": BASE,
                      "note": "no zero-cost auth probe in the published spec; "
                              "auth checks configuration only."}, indent=2))


def cmd_compose(args):
    payload = {
        "prompt": {"text": args.prompt},
        "format": args.format,
        "looping": args.looping,
    }
    result = call_api("POST", "/api/v1/tracks/compose", payload=payload)
    task_id = result.get("task_id")
    print(json.dumps({"ok": True, "status": result.get("status"),
                      "task_id": task_id}, indent=2))
    print(f"poll with: bin/beatoven.py status --task-id {task_id}", file=sys.stderr)


def cmd_status(args):
    result = call_api("GET", f"/api/v1/tasks/{args.task_id}")
    meta = result.get("meta", {}) if isinstance(result, dict) else {}
    out = {
        "status": result.get("status"),
        "task_id": args.task_id,
        "track_id": meta.get("track_id"),
        "track_url": meta.get("track_url"),
        "stems_url": meta.get("stems_url"),
    }
    print(json.dumps(out, indent=2))
    if result.get("status") == "composed":
        print(f"download with: bin/beatoven.py download --task-id {args.task_id} --out track.wav",
              file=sys.stderr)


def cmd_download(args):
    if args.url:
        track_url = args.url
    else:
        result = call_api("GET", f"/api/v1/tasks/{args.task_id}")
        if result.get("status") != "composed":
            sys.exit(f"error: task status is '{result.get('status')}', not composed; poll status first")
        track_url = (result.get("meta") or {}).get("track_url")
        if not track_url:
            sys.exit("error: composed task returned no track_url")
    download_url(track_url, args.out)
    print(json.dumps({"ok": True, "saved": args.out}, indent=2))


def cmd_stems(args):
    result = call_api("GET", f"/api/v1/tasks/{args.task_id}")
    if result.get("status") != "composed":
        sys.exit(f"error: task status is '{result.get('status')}', not composed; poll status first")
    stems = (result.get("meta") or {}).get("stems_url") or {}
    if args.stem:
        url = stems.get(args.stem)
        if not url:
            sys.exit(f"error: no '{args.stem}' stem in response (have: {sorted(stems)})")
        if args.out:
            download_url(url, args.out)
            print(json.dumps({"ok": True, "stem": args.stem, "saved": args.out}, indent=2))
        else:
            print(json.dumps({"stem": args.stem, "url": url}, indent=2))
    else:
        print(json.dumps({"task_id": args.task_id, "stems_url": stems}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Beatoven.ai API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify credential configuration (no spend)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("compose", help="compose a track (confirm first; metered)")
    p.add_argument("--prompt", required=True,
                   help='e.g. "30 seconds peaceful lo-fi chill hop track"')
    p.add_argument("--format", default="wav", choices=["mp3", "aac", "wav"])
    p.add_argument("--looping", action="store_true",
                   help="higher looping amount (default: false)")
    p.set_defaults(func=cmd_compose)

    p = sub.add_parser("status", help="poll a composition task")
    p.add_argument("--task-id", required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("download", help="download a composed track")
    p.add_argument("--task-id", default=None)
    p.add_argument("--url", default=None, help="track_url directly")
    p.add_argument("--out", required=True, help="local output path")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("stems", help="list or download individual stems (bass/chords/melody/percussion)")
    p.add_argument("--task-id", required=True)
    p.add_argument("--stem", default=None, choices=["bass", "chords", "melody", "percussion"])
    p.add_argument("--out", default=None, help="local output path (downloads that stem)")
    p.set_defaults(func=cmd_stems)

    args = parser.parse_args()
    if args.command == "download" and not (args.task_id or args.url):
        parser.error("download needs --task-id or --url")
    args.func(args)


if __name__ == "__main__":
    main()
