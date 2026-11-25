#!/usr/bin/env python3
"""Minimal Prusa Connect cloud API CLI for the muse-connectors prusa-connect
skill.

Auth: loads the per-user `custom.prusa-connect` personal API token as a
surrogate via the bundled dynamic_credentials helper, sent as
`Authorization: Bearer <token>`. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to
connect.prusa3d.com. Create the token in the Prusa Connect web UI under
Settings > API Access.

READS ship fully (printers, jobs, files, cameras, stats). File upload ships
against the documented POST /api/files path but its payload shape is
unverified: treat it as untested.

Job pause/resume/cancel/restart are deliberately NOT shipped: their exact
write paths could not be pinned from the official Prusa Connect docs or the
community SDK mirror at build time, and this connector never guesses paths.
See the skill's Maturity section for the open item.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.prusa-connect"
PROVIDER_ID = "prusa-connect"
API = "https://connect.prusa3d.com"
ALLOWED_HOSTS = ("connect.prusa3d.com",)
CONFIRM_FILE = os.path.expanduser(
    "~/.cache/muse-connectors/prusa-connect/confirmed.json"
)

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        add_surrogate_to_request,
        dynamic_credential_entry,
        read_json_response,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def credential_available() -> bool:
    try:
        dynamic_credential_entry(CREDENTIAL_NAME)
        return True
    except Exception:
        return False


def connect_guidance() -> str:
    return (
        f"no credential stored as {CREDENTIAL_NAME}. Create a personal API "
        f"token in the Prusa Connect web UI (Settings > API Access), then run "
        f"the secure credential flow (credentials.request_api_access) for "
        f"provider '{PROVIDER_ID}' and store the token as {CREDENTIAL_NAME}, "
        f"then re-run."
    )


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME,
                                 allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}\n{connect_guidance()}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: prusa connect returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


# ---- confirmation helpers ------------------------------------------------

def _load_confirmed() -> set:
    try:
        with open(CONFIRM_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def _record_confirmed(key: str) -> None:
    try:
        os.makedirs(os.path.dirname(CONFIRM_FILE), exist_ok=True)
        confirmed = _load_confirmed()
        confirmed.add(key)
        with open(CONFIRM_FILE, "w") as f:
            json.dump(sorted(confirmed), f)
    except Exception:
        pass  # non-fatal: the user will simply be asked again next time


def require_medium_confirm(device: str, action: str, effect: str,
                           confirm: str | None) -> None:
    key = f"{device}:{action}"
    if key in _load_confirmed():
        return
    if confirm != effect:
        sys.exit(
            f"error: this is a MEDIUM actuation ({effect}).\n"
            f"First use on this printer requires --confirm \"{effect}\".\n"
            "After the first confirmation, later runs proceed without asking."
        )
    _record_confirmed(key)


# ---- commands ------------------------------------------------------------

def cmd_auth(_args):
    if not credential_available():
        print(json.dumps({
            "ok": False, "connected": False, "provider": PROVIDER_ID,
            "connect": connect_guidance(),
        }, indent=2))
        return
    result = call("GET", "/api/printers")
    printers = result.get("printers", result if isinstance(result, list) else [])
    count = len(printers) if isinstance(printers, list) else "?"
    print(json.dumps({"ok": True, "provider": PROVIDER_ID,
                      "printers": count}, indent=2))


def _printer_list() -> list:
    result = call("GET", "/api/printers")
    if isinstance(result, list):
        return result
    return result.get("printers", [])


def cmd_printers(_args):
    printers = _printer_list()
    print(json.dumps([
        {"id": p.get("id"), "name": p.get("name"),
         "state": p.get("printer_state") or p.get("state"),
         "job": (p.get("job") or {}).get("id") if isinstance(p.get("job"), dict) else p.get("job")}
        for p in printers
    ], indent=2))


def cmd_jobs(_args):
    result = call("GET", "/api/jobs")
    jobs = result if isinstance(result, list) else result.get("jobs", [])
    print(json.dumps(jobs, indent=2))


def cmd_files(args):
    params = {}
    if args.printer_id:
        params["printer"] = args.printer_id
    result = call("GET", "/api/files", params=params or None)
    files = result if isinstance(result, list) else result.get("files", [])
    print(json.dumps(files, indent=2))


def cmd_cameras(_args):
    result = call("GET", "/api/cameras")
    cameras = result if isinstance(result, list) else result.get("cameras", [])
    print(json.dumps(cameras, indent=2))


def cmd_stats(_args):
    result = call("GET", "/api/stats")
    print(json.dumps(result, indent=2))


def cmd_upload(args):
    if not os.path.isfile(args.path):
        sys.exit(f"error: file not found: {args.path}")
    filename = os.path.basename(args.path)
    effect = f"upload {filename} to Prusa Connect printer storage"
    require_medium_confirm("prusa-connect", "upload", effect, args.confirm)
    print("warning: the POST /api/files upload payload is untested in this "
          "build; verify the result in the Prusa Connect web UI",
          file=sys.stderr)
    boundary = uuid.uuid4().hex
    ctype, _ = mimetypes.guess_type(filename)
    with open(args.path, "rb") as f:
        file_bytes = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {ctype or 'application/octet-stream'}\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        API + "/api/files", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME,
                                 allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}\n{connect_guidance()}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: prusa connect upload returned HTTP {exc.code}")
    except Exception as exc:
        sys.exit(f"error: upload failed: {exc}")
    print(json.dumps({"ok": True, "effect": effect,
                      "response": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Prusa Connect cloud API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("printers", help="list printers and their state")
    p.set_defaults(func=cmd_printers)

    p = sub.add_parser("jobs", help="list jobs and their status")
    p.set_defaults(func=cmd_jobs)

    p = sub.add_parser("files", help="list files in printer storage")
    p.add_argument("--printer-id", default=None,
                   help="filter to one printer")
    p.set_defaults(func=cmd_files)

    p = sub.add_parser("cameras", help="list printer cameras")
    p.set_defaults(func=cmd_cameras)

    p = sub.add_parser("stats", help="print statistics")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("upload",
                       help="upload a .gcode file (MEDIUM: confirm first use; "
                            "payload untested)")
    p.add_argument("--path", required=True, help="local .gcode file")
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "upload benchy.gcode to Prusa Connect printer storage"')
    p.set_defaults(func=cmd_upload)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
