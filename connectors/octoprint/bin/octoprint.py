#!/usr/bin/env python3
"""Minimal OctoPrint REST API CLI for the muse-connectors octoprint skill.

Auth: loads the per-user `custom.octoprint` API key as a surrogate via the
bundled dynamic_credentials helper, sent as the `X-Api-Key` request header
(or `?apikey=` query param). The real key never touches this script: the
runtime swaps the surrogate on approved egress, only to the host given by
--host.

The API key is generated in OctoPrint under Settings > Application Keys (or
the global API key). Default host is http://localhost:5000; point --host at
your OctoPrint instance (remote access via OctoEverywhere relay, VPN, or a
reverse proxy).

Confirmation rules:
- HIGH (raw G-code): requires BOTH --enable-raw-gcode (capability flag) AND
  --confirm "run raw G-code: <command>" on EVERY call. Raw G-code can
  physically damage the printer.
- MEDIUM (job start/pause/cancel/restart, file upload/select, heater
  targets): --confirm "<exact physical effect>" on first use per printer,
  then proceed.
- LOW (axis jog/home, serial connect/disconnect, reads): no confirmation.
  Disconnecting mid-print cancels the print; the CLI warns but proceeds.
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
CREDENTIAL_NAME = "custom.octoprint"
PROVIDER_ID = "octoprint"
CONFIRM_FILE = os.path.expanduser(
    "~/.cache/muse-connectors/octoprint/confirmed.json"
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


def normalize_host(raw: str) -> str:
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        sys.exit("error: --host is empty")
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        sys.exit(f"error: --host is not a valid http(s) URL: {raw!r}")
    return raw


def credential_available() -> bool:
    try:
        dynamic_credential_entry(CREDENTIAL_NAME)
        return True
    except Exception:
        return False


def connect_guidance() -> str:
    return (
        f"no credential stored as {CREDENTIAL_NAME}. Generate an API key in "
        f"OctoPrint (Settings > Application Keys), then run the secure "
        f"credential flow (credentials.request_api_access) for provider "
        f"'{PROVIDER_ID}' and store the key as {CREDENTIAL_NAME}, then re-run."
    )


def make_opener(insecure: bool):
    if not insecure:
        return urllib.request.build_opener()
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx))


class OctoPrint:
    def __init__(self, host: str, insecure: bool = False):
        self.base = normalize_host(host)
        self.hostname = urllib.parse.urlsplit(self.base).hostname or ""
        self.opener = make_opener(insecure)
        if insecure:
            print("warning: TLS verification disabled (--insecure)",
                  file=sys.stderr)

    def call(self, method: str, path: str,
             params: dict | None = None,
             payload: dict | None = None) -> dict | None:
        url = self.base + path
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)
        try:
            add_surrogate_to_request(req, CREDENTIAL_NAME,
                                     allowed_hosts=(self.hostname,))
        except DynamicCredentialError as exc:
            sys.exit(f"error: credential problem: {exc}\n{connect_guidance()}")
        try:
            with self.opener.open(req, timeout=30) as resp:
                if resp.status == 204:
                    return None
                return read_json_response(resp)
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
                msg = body[:300] or str(exc)
            except Exception:
                msg = str(exc)
            sys.exit(f"error: octoprint returned HTTP {exc.code}: {msg}")
        except Exception as exc:  # network-level failure
            sys.exit(f"error: request failed: {exc}")

    def upload(self, local_path: str, dest_filename: str | None) -> dict:
        boundary = uuid.uuid4().hex
        filename = dest_filename or os.path.basename(local_path)
        ctype, _ = mimetypes.guess_type(filename)
        with open(local_path, "rb") as f:
            file_bytes = f.read()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {ctype or 'application/octet-stream'}\r\n\r\n"
        ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            self.base + "/api/files/local", data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            add_surrogate_to_request(req, CREDENTIAL_NAME,
                                     allowed_hosts=(self.hostname,))
        except DynamicCredentialError as exc:
            sys.exit(f"error: credential problem: {exc}\n{connect_guidance()}")
        try:
            with self.opener.open(req, timeout=120) as resp:
                return read_json_response(resp)
        except urllib.error.HTTPError as exc:
            sys.exit(f"error: octoprint upload returned HTTP {exc.code}")
        except Exception as exc:
            sys.exit(f"error: upload failed: {exc}")


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


def require_high_raw_gcode(command: str, enabled: bool,
                           confirm: str | None) -> None:
    if not enabled:
        sys.exit(
            "error: raw G-code is HIGH risk (it can physically damage the "
            "printer). Re-run with --enable-raw-gcode to acknowledge this."
        )
    effect = f"run raw G-code: {command}"
    if confirm != effect:
        sys.exit(
            f"error: HIGH actuation ({effect}).\n"
            f"Re-run with --confirm \"{effect}\" to confirm this exact command."
        )


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

def new_client(args) -> OctoPrint:
    host = args.host or os.environ.get("OCTOPRINT_HOST") or "http://localhost:5000"
    return OctoPrint(host, insecure=args.insecure)


def cmd_auth(args):
    if not credential_available():
        print(json.dumps({
            "ok": False, "connected": False, "provider": PROVIDER_ID,
            "connect": connect_guidance(),
        }, indent=2))
        return
    client = new_client(args)
    result = client.call("GET", "/api/printer") or {}
    state = (result.get("state") or {})
    print(json.dumps({"ok": True, "provider": PROVIDER_ID,
                      "printer_state": state.get("text")}, indent=2))


def cmd_version(args):
    client = new_client(args)
    print(json.dumps(client.call("GET", "/api/version") or {}, indent=2))


def cmd_status(args):
    client = new_client(args)
    result = client.call("GET", "/api/printer") or {}
    temps = result.get("temperature", {})
    print(json.dumps({
        "state": (result.get("state") or {}).get("text"),
        "tool0": {"actual": (temps.get("tool0") or {}).get("actual"),
                  "target": (temps.get("tool0") or {}).get("target")},
        "bed": {"actual": (temps.get("bed") or {}).get("actual"),
                "target": (temps.get("bed") or {}).get("target")},
    }, indent=2))


def cmd_job(args):
    client = new_client(args)
    result = client.call("GET", "/api/job") or {}
    print(json.dumps({
        "state": result.get("state"),
        "file": ((result.get("job") or {}).get("file") or {}).get("name"),
        "progress": result.get("progress", {}),
    }, indent=2))


def cmd_job_cmd(args):
    client = new_client(args)
    device = client.hostname
    effect = f"{args.command} the print job on {device}"
    require_medium_confirm(device, f"job-{args.command}", effect, args.confirm)
    client.call("POST", "/api/job", payload={"command": args.command})
    print(json.dumps({"ok": True, "command": args.command,
                      "effect": effect}, indent=2))


def cmd_files(args):
    client = new_client(args)
    result = client.call("GET", "/api/files",
                         params={"recursive": "true"}) or {}
    def walk(node, out):
        if node.get("type") == "machinecode":
            out.append({"path": node.get("path"), "name": node.get("name"),
                        "size": node.get("size")})
        for child in node.get("children", []) or []:
            walk(child, out)
        return out
    files = []
    for node in result.get("files", []) or []:
        walk(node, files)
    print(json.dumps(files, indent=2))


def cmd_upload(args):
    client = new_client(args)
    if not os.path.isfile(args.path):
        sys.exit(f"error: file not found: {args.path}")
    effect = f"upload {os.path.basename(args.path)} to {client.hostname}"
    require_medium_confirm(client.hostname, "upload", effect, args.confirm)
    result = client.upload(args.path, args.dest)
    print(json.dumps({"ok": True, "effect": effect,
                      "path": (result.get("files") or {})
                      .get("local", {}).get("path")}, indent=2))


def cmd_file_select(args):
    client = new_client(args)
    effect = f"select file {args.path} for printing on {client.hostname}"
    require_medium_confirm(client.hostname, "file-select", effect,
                           args.confirm)
    client.call("POST", f"/api/files/local/{args.path}",
                payload={"command": "select"})
    print(json.dumps({"ok": True, "effect": effect}, indent=2))


def cmd_tool_temp(args):
    client = new_client(args)
    effect = (f"heat {args.tool} to {args.temp}C on {client.hostname} "
              f"(physical heater)")
    require_medium_confirm(client.hostname, f"tool-temp-{args.tool}", effect,
                           args.confirm)
    client.call("POST", "/api/printer/tool",
                payload={"command": "target",
                         "targets": {args.tool: args.temp}})
    print(json.dumps({"ok": True, "effect": effect}, indent=2))


def cmd_bed_temp(args):
    client = new_client(args)
    effect = (f"heat the print bed to {args.temp}C on {client.hostname} "
              f"(physical heater)")
    require_medium_confirm(client.hostname, "bed-temp", effect, args.confirm)
    client.call("POST", "/api/printer/bed",
                payload={"command": "target", "target": args.temp})
    print(json.dumps({"ok": True, "effect": effect}, indent=2))


def cmd_printhead(args):
    client = new_client(args)
    if args.command == "jog":
        payload = {"command": "jog"}
        for axis in ("x", "y", "z"):
            val = getattr(args, axis)
            if val is not None:
                payload[axis] = val
        if len(payload) == 1:
            sys.exit("error: jog needs at least one of --x, --y, --z")
    else:
        payload = {"command": "home"}
        axes = [a for a in ("x", "y", "z") if getattr(args, a + "_home")]
        if axes:
            payload["axes"] = axes
    client.call("POST", "/api/printer/printhead", payload=payload)
    print(json.dumps({"ok": True, "command": args.command,
                      "payload": payload}, indent=2))


def cmd_gcode(args):
    client = new_client(args)
    require_high_raw_gcode(args.command, args.enable_raw_gcode, args.confirm)
    client.call("POST", "/api/printer/command",
                payload={"command": args.command})
    print(json.dumps({"ok": True, "effect": f"run raw G-code: {args.command}"},
                     indent=2))


def cmd_connection(args):
    client = new_client(args)
    if args.action == "disconnect":
        print("warning: disconnecting mid-print cancels the print",
              file=sys.stderr)
    client.call("POST", "/api/connection",
                payload={"command": args.action})
    print(json.dumps({"ok": True, "action": args.action}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="OctoPrint REST API CLI (muse-connectors)")
    parser.add_argument("--host", default=None,
                        help="OctoPrint base URL (default: $OCTOPRINT_HOST or "
                             "http://localhost:5000)")
    parser.add_argument("--insecure", action="store_true",
                        help="skip TLS verification (self-signed reverse proxy)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("version", help="OctoPrint server version")
    p.set_defaults(func=cmd_version)

    p = sub.add_parser("status", help="printer state and temperatures")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("job", help="current print job progress")
    p.set_defaults(func=cmd_job)

    p = sub.add_parser("job-cmd",
                       help="start/pause/cancel/restart the print job "
                            "(MEDIUM: confirm first use)")
    p.add_argument("--command", required=True,
                   choices=["start", "cancel", "restart", "pause", "toggle"])
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "start the print job on octopi.local"')
    p.set_defaults(func=cmd_job_cmd)

    p = sub.add_parser("files", help="list gcode files on the printer")
    p.set_defaults(func=cmd_files)

    p = sub.add_parser("upload", help="upload a gcode file (MEDIUM: confirm first use)")
    p.add_argument("--path", required=True, help="local .gcode file")
    p.add_argument("--dest", default=None, help="destination filename")
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "upload benchy.gcode to octopi.local"')
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("file-select",
                       help="select a file for printing (MEDIUM: confirm first use)")
    p.add_argument("--path", required=True, help="file path on the printer")
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "select file benchy.gcode for printing on octopi.local"')
    p.set_defaults(func=cmd_file_select)

    p = sub.add_parser("tool-temp",
                       help="set hotend target temp (MEDIUM: confirm first use)")
    p.add_argument("--tool", default="tool0")
    p.add_argument("--temp", type=int, required=True, help="target Celsius")
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "heat tool0 to 210C on octopi.local (physical heater)"')
    p.set_defaults(func=cmd_tool_temp)

    p = sub.add_parser("bed-temp",
                       help="set bed target temp (MEDIUM: confirm first use)")
    p.add_argument("--temp", type=int, required=True, help="target Celsius")
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "heat the print bed to 60C on octopi.local (physical heater)"')
    p.set_defaults(func=cmd_bed_temp)

    p = sub.add_parser("printhead", help="jog or home axes (LOW)")
    p.add_argument("--command", required=True, choices=["jog", "home"])
    p.add_argument("--x", type=float, default=None)
    p.add_argument("--y", type=float, default=None)
    p.add_argument("--z", type=float, default=None)
    p.add_argument("--x-home", action="store_true")
    p.add_argument("--y-home", action="store_true")
    p.add_argument("--z-home", action="store_true")
    p.set_defaults(func=cmd_printhead)

    p = sub.add_parser("gcode",
                       help="run raw G-code (HIGH: needs --enable-raw-gcode and --confirm)")
    p.add_argument("--command", required=True, help='e.g. "G28"')
    p.add_argument("--enable-raw-gcode", action="store_true",
                   help="acknowledge that raw G-code can damage the printer")
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "run raw G-code: G28"')
    p.set_defaults(func=cmd_gcode)

    p = sub.add_parser("connection",
                       help="connect/disconnect the printer serial link (LOW)")
    p.add_argument("--action", required=True, choices=["connect", "disconnect"])
    p.set_defaults(func=cmd_connection)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
