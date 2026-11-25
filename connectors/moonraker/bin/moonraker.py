#!/usr/bin/env python3
"""Minimal Moonraker API CLI for the muse-connectors moonraker skill.

Moonraker (the API server for Klipper printers) has NO auth on the LAN by
default; the CLI works without any credential in that case. If the printer's
[authorization] config enables API keys, pass --api-key to attach the stored
`custom.moonraker` credential as a surrogate: the key value is never passed
on the command line, in the environment, or in a file.

Default host is http://localhost:7125; point --host at the printer
(remote access via OctoEverywhere relay, VPN, or a reverse proxy).

Confirmation rules:
- HIGH (raw G-code via /printer/gcode/script): requires BOTH
  --enable-raw-gcode (capability flag) AND --confirm "run raw G-code script:
  <script>" on EVERY call. Raw G-code can physically damage the printer.
- MEDIUM (print start/pause/resume/cancel, emergency stop, file upload,
  smart-plug power): --confirm "<exact physical effect>" on first use per
  printer, then proceed.
- LOW (reads): no confirmation.
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
CREDENTIAL_NAME = "custom.moonraker"
PROVIDER_ID = "moonraker"
CONFIRM_FILE = os.path.expanduser(
    "~/.cache/muse-connectors/moonraker/confirmed.json"
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
        f"no credential stored as {CREDENTIAL_NAME}, but --api-key was passed. "
        f"Enable [authorization] on Moonraker and store the API key via the "
        f"secure credential flow (credentials.request_api_access) for provider "
        f"'{PROVIDER_ID}' as {CREDENTIAL_NAME}, then re-run. Omit --api-key "
        f"entirely when Moonraker runs with default (no) LAN auth."
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


class Moonraker:
    def __init__(self, host: str, insecure: bool = False,
                 use_api_key: bool = False):
        self.base = normalize_host(host)
        self.hostname = urllib.parse.urlsplit(self.base).hostname or ""
        self.opener = make_opener(insecure)
        self.use_api_key = use_api_key
        if insecure:
            print("warning: TLS verification disabled (--insecure)",
                  file=sys.stderr)
        if use_api_key and not credential_available():
            sys.exit(f"error: {connect_guidance()}")

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
        if self.use_api_key:
            try:
                add_surrogate_to_request(req, CREDENTIAL_NAME,
                                         allowed_hosts=(self.hostname,))
            except DynamicCredentialError as exc:
                sys.exit(f"error: credential problem: {exc}\n"
                         f"{connect_guidance()}")
        try:
            with self.opener.open(req, timeout=30) as resp:
                if resp.status == 204:
                    return None
                body = read_json_response(resp)
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
                msg = body[:300] or str(exc)
            except Exception:
                msg = str(exc)
            sys.exit(f"error: moonraker returned HTTP {exc.code}: {msg}")
        except Exception as exc:  # network-level failure
            sys.exit(f"error: request failed: {exc}")
        if isinstance(body, dict) and body.get("error"):
            sys.exit(f"error: moonraker error: "
                     f"{json.dumps(body['error'])[:300]}")
        return body

    def upload(self, local_path: str, root: str = "gcodes") -> dict:
        boundary = uuid.uuid4().hex
        filename = os.path.basename(local_path)
        ctype, _ = mimetypes.guess_type(filename)
        with open(local_path, "rb") as f:
            file_bytes = f.read()
        parts = []
        for name, value in (("root", root),):
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n".encode("utf-8"))
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {ctype or 'application/octet-stream'}\r\n\r\n"
            .encode("utf-8") + file_bytes + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)
        req = urllib.request.Request(
            self.base + "/server/files/upload", data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        if self.use_api_key:
            try:
                add_surrogate_to_request(req, CREDENTIAL_NAME,
                                         allowed_hosts=(self.hostname,))
            except DynamicCredentialError as exc:
                sys.exit(f"error: credential problem: {exc}\n"
                         f"{connect_guidance()}")
        try:
            with self.opener.open(req, timeout=120) as resp:
                return read_json_response(resp)
        except urllib.error.HTTPError as exc:
            sys.exit(f"error: moonraker upload returned HTTP {exc.code}")
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


def require_high_raw_gcode(script: str, enabled: bool,
                           confirm: str | None) -> None:
    if not enabled:
        sys.exit(
            "error: raw G-code is HIGH risk (it can physically damage the "
            "printer). Re-run with --enable-raw-gcode to acknowledge this."
        )
    effect = f"run raw G-code script: {script}"
    if confirm != effect:
        sys.exit(
            f"error: HIGH actuation ({effect}).\n"
            f"Re-run with --confirm \"{effect}\" to confirm this exact script."
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

def new_client(args) -> Moonraker:
    host = args.host or os.environ.get("MOONRAKER_HOST") or "http://localhost:7125"
    return Moonraker(host, insecure=args.insecure, use_api_key=args.api_key)


def cmd_auth(args):
    # auth never crashes: no credential is the normal LAN case.
    client = Moonraker(
        args.host or os.environ.get("MOONRAKER_HOST") or "http://localhost:7125",
        insecure=args.insecure, use_api_key=False)
    result = client.call("GET", "/server/info") or {}
    info = result.get("result", {})
    print(json.dumps({
        "ok": True, "provider": PROVIDER_ID,
        "moonraker_version": info.get("moonraker_version"),
        "klippy_state": info.get("klippy_state"),
        "api_key_stored": credential_available(),
        "note": ("LAN is unauthenticated by default; omit --api-key unless "
                 "[authorization] is enabled on Moonraker"),
    }, indent=2))


def cmd_status(args):
    client = new_client(args)
    result = client.call(
        "GET", "/printer/objects/query",
        params={"print_stats": "", "extruder": "", "heater_bed": ""}) or {}
    r = result.get("result", {}).get("status", {})
    stats = r.get("print_stats", {})
    extruder = r.get("extruder", {})
    bed = r.get("heater_bed", {})
    print(json.dumps({
        "state": stats.get("state"),
        "filename": stats.get("filename"),
        "print_duration": stats.get("print_duration"),
        "extruder_temp": extruder.get("temperature"),
        "extruder_target": extruder.get("target"),
        "bed_temp": bed.get("temperature"),
        "bed_target": bed.get("target"),
    }, indent=2))


def cmd_files(args):
    client = new_client(args)
    result = client.call("GET", "/server/files/list",
                         params={"root": "gcodes"}) or {}
    files = (result.get("result") or [])
    print(json.dumps([
        {"path": f.get("path"), "size": f.get("size"),
         "modified": f.get("modified")}
        for f in files
    ], indent=2))


def cmd_upload(args):
    client = new_client(args)
    if not os.path.isfile(args.path):
        sys.exit(f"error: file not found: {args.path}")
    effect = f"upload {os.path.basename(args.path)} to {client.hostname}"
    require_medium_confirm(client.hostname, "upload", effect, args.confirm)
    result = client.upload(args.path)
    print(json.dumps({"ok": True, "effect": effect,
                      "result": result.get("result")}, indent=2))


def cmd_print_start(args):
    client = new_client(args)
    effect = f"start printing {args.filename} on {client.hostname}"
    require_medium_confirm(client.hostname, "print-start", effect,
                           args.confirm)
    client.call("POST", "/printer/print/start",
                params={"filename": args.filename})
    print(json.dumps({"ok": True, "effect": effect}, indent=2))


def _print_simple(args, action: str, verb: str):
    client = new_client(args)
    effect = f"{verb} the print on {client.hostname}"
    require_medium_confirm(client.hostname, f"print-{action}", effect,
                           args.confirm)
    client.call("POST", f"/printer/print/{action}")
    print(json.dumps({"ok": True, "effect": effect}, indent=2))


def cmd_print_pause(args):
    _print_simple(args, "pause", "pause")


def cmd_print_resume(args):
    _print_simple(args, "resume", "resume")


def cmd_print_cancel(args):
    _print_simple(args, "cancel", "cancel")


def cmd_emergency_stop(args):
    client = new_client(args)
    effect = f"emergency stop on {client.hostname}: halt all motion and heaters"
    require_medium_confirm(client.hostname, "emergency-stop", effect,
                           args.confirm)
    client.call("POST", "/printer/emergency_stop")
    print(json.dumps({"ok": True, "effect": effect}, indent=2))


def cmd_gcode_script(args):
    client = new_client(args)
    require_high_raw_gcode(args.script, args.enable_raw_gcode, args.confirm)
    client.call("POST", "/printer/gcode/script",
                params={"script": args.script})
    print(json.dumps({"ok": True,
                      "effect": f"run raw G-code script: {args.script}"},
                     indent=2))


def cmd_device_power(args):
    client = new_client(args)
    effect = f"turn smart-plug device {args.device} {args.action} on {client.hostname}"
    require_medium_confirm(client.hostname, f"device-power-{args.device}",
                           effect, args.confirm)
    client.call("POST", "/machine/device_power/device",
                params={"device": args.device, "action": args.action})
    print(json.dumps({"ok": True, "effect": effect}, indent=2))


def add_common(p):
    p.add_argument("--host", default=None,
                   help="Moonraker base URL (default: $MOONRAKER_HOST or "
                        "http://localhost:7125)")
    p.add_argument("--insecure", action="store_true",
                   help="skip TLS verification (self-signed reverse proxy)")
    p.add_argument("--api-key", action="store_true",
                   help="attach the stored custom.moonraker credential "
                        "(for [authorization]-enabled printers; the key is "
                        "never passed on the command line)")
    p.add_argument("--confirm", default=None,
                   help="exact physical-effect text for MEDIUM actuations "
                        "(required on first use per printer)")


def main():
    parser = argparse.ArgumentParser(
        description="Moonraker API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="server info; never requires a credential")
    add_common(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("status", help="print state and temperatures")
    add_common(p)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("files", help="list gcode files")
    add_common(p)
    p.set_defaults(func=cmd_files)

    p = sub.add_parser("upload", help="upload a gcode file (MEDIUM: confirm first use)")
    add_common(p)
    p.add_argument("--path", required=True, help="local .gcode file")
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("print-start",
                       help="start a print (MEDIUM: confirm first use)")
    add_common(p)
    p.add_argument("--filename", required=True,
                   help="file name on the printer, e.g. benchy.gcode")
    p.set_defaults(func=cmd_print_start)

    for action, verb in (("print-pause", "pause"), ("print-resume", "resume"),
                         ("print-cancel", "cancel")):
        p = sub.add_parser(action, help=f"{verb} the print (MEDIUM: confirm first use)")
        add_common(p)
        p.set_defaults(func={"print-pause": cmd_print_pause,
                             "print-resume": cmd_print_resume,
                             "print-cancel": cmd_print_cancel}[action])

    p = sub.add_parser("emergency-stop",
                       help="halt all motion and heaters (MEDIUM: confirm first use)")
    add_common(p)
    p.set_defaults(func=cmd_emergency_stop)

    p = sub.add_parser("gcode-script",
                       help="run raw G-code (HIGH: needs --enable-raw-gcode and --confirm)")
    add_common(p)
    p.add_argument("--script", required=True, help='e.g. "G28"')
    p.add_argument("--enable-raw-gcode", action="store_true",
                   help="acknowledge that raw G-code can damage the printer")
    p.set_defaults(func=cmd_gcode_script)

    p = sub.add_parser("device-power",
                       help="toggle a smart-plug device (MEDIUM: confirm first use)")
    add_common(p)
    p.add_argument("--device", required=True, help="device name in Moonraker")
    p.add_argument("--action", required=True, choices=["on", "off"])
    p.set_defaults(func=cmd_device_power)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
