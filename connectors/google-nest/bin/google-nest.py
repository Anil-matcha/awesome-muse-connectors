#!/usr/bin/env python3
"""Minimal Google Nest Smart Device Management (SDM) API CLI.

Auth: OAuth 2.0 access token, stored as the per-user `custom.google-nest`
credential and loaded as a surrogate via the bundled dynamic_credentials
helper. Scope: https://www.googleapis.com/auth/sdm.service. The real token
never touches this script: the runtime swaps the surrogate on approved
egress, only to smartdevicemanagement.googleapis.com.

Physical-world safety: thermostat commands are MEDIUM actuations (they start
or stop real HVAC) and need --confirm "<exact physical effect>" on first use
per device, then proceed (confirmations recorded locally). Camera live-stream
generation is LOW: it proceeds with a logged notice. Cameras and doorbells are
otherwise read-only traits.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.google-nest"
ALLOWED_HOSTS = ("smartdevicemanagement.googleapis.com",)
API = "https://smartdevicemanagement.googleapis.com/v1"
CONFIRM_FILE = os.path.expanduser("~/.config/muse-connectors/google-nest/confirmed.json")

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


# ---------------------------------------------------------------------------
# Physical-world confirmation gating
# ---------------------------------------------------------------------------

def load_confirmed() -> set:
    try:
        with open(CONFIRM_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return set(data) if isinstance(data, list) else set()
    except (OSError, json.JSONDecodeError):
        return set()


def save_confirmed(confirmed: set) -> None:
    os.makedirs(os.path.dirname(CONFIRM_FILE), exist_ok=True)
    with open(CONFIRM_FILE, "w", encoding="utf-8") as fh:
        json.dump(sorted(confirmed), fh, indent=2)


def require_medium(device: str, action_class: str, confirm: str | None,
                   effect: str) -> None:
    confirmed = load_confirmed()
    key = f"{device}:{action_class}"
    if key in confirmed:
        return
    if not confirm or len(confirm.strip()) < 3:
        sys.exit(
            "error: first MEDIUM actuation on this device is confirmation-gated. "
            f"This command would: {effect}. Re-run with --confirm "
            "\"<exact physical effect>\"; later runs on this device proceed "
            "without re-confirming."
        )
    confirmed.add(key)
    save_confirmed(confirmed)
    print(
        f"notice: MEDIUM actuation confirmed and recorded for device "
        f"{device} ({action_class}); future runs on it proceed without "
        f"re-confirming. Said: {confirm.strip()}",
        file=sys.stderr,
    )


def low_notice(effect: str) -> None:
    print(f"notice: LOW actuation proceeding: {effect}", file=sys.stderr)


# ---------------------------------------------------------------------------
# API plumbing
# ---------------------------------------------------------------------------

def call(method: str, path: str, payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError:
        print(
            "not connected: no custom.google-nest credential is stored.\n"
            "Collect it via the secure credential flow "
            "(credentials.request_api_access) as an OAuth 2.0 access token "
            "with scope https://www.googleapis.com/auth/sdm.service for your "
            "Device Access project, then retry. "
            "See this skill's SKILL.md Auth section.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = (body.get("error") or {}).get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: nest SDM returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def enterprise(args) -> str:
    return f"/enterprises/{args.project}"


def parse_value(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_auth(args):
    result = call("GET", enterprise(args) + "/structures")
    structs = result.get("structures", [])
    print(json.dumps({
        "ok": True,
        "structures": [{"name": s.get("name"),
                        "displayName": (s.get("traits") or {})
                        .get("sdm.devices.traits.Info", {})
                        .get("customName", "")}
                       for s in structs],
    }, indent=2))


def cmd_structures(args):
    result = call("GET", enterprise(args) + "/structures")
    print(json.dumps(result.get("structures", []), indent=2))


def cmd_devices(args):
    result = call("GET", enterprise(args) + "/devices")
    devices = result.get("devices", [])
    print(json.dumps([
        {"name": d.get("name"), "type": d.get("type"),
         "traits": sorted((d.get("traits") or {}).keys())}
        for d in devices
    ], indent=2))


def cmd_device(args):
    result = call("GET", enterprise(args) + f"/devices/{args.id}")
    print(json.dumps(result, indent=2))


def cmd_execute(args):
    command = args.command
    params = {}
    for pair in args.param:
        if "=" not in pair:
            sys.exit("error: --param must be KEY=VALUE")
        k, _, v = pair.partition("=")
        params[k] = parse_value(v)
    full_command = ("sdm.devices.commands." + command
                    if not command.startswith("sdm.devices.commands.")
                    else command)

    # --- actuation-risk grading ---
    if full_command == "sdm.devices.commands.CameraLiveStream.GenerateRtspStream":
        low_notice(f"generate an RTSP live-stream URL for camera {args.id} "
                   "(non-physical; the URL expires)")
    else:
        require_medium(args.id, "execute", args.confirm,
                       f"execute {full_command} on device {args.id} "
                       f"with params {params} (thermostat commands start or "
                       "stop real HVAC)")

    result = call("POST", enterprise(args) + f"/devices/{args.id}:executeCommand",
                  {"command": full_command, "params": params})
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Google Nest SDM API CLI (muse-connectors). --project is "
                    "the Device Access project id. Thermostat commands are "
                    "MEDIUM actuations (first use per device needs --confirm); "
                    "camera stream generation is LOW and proceeds with a "
                    "notice.")
    parser.add_argument("--project", required=True,
                        help="Device Access project id (the enterprise id)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="status check: list structures, verify token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("structures", help="list structures (homes)")
    p.set_defaults(func=cmd_structures)

    p = sub.add_parser("devices", help="list devices with their traits")
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("device", help="read one device's traits")
    p.add_argument("--id", required=True, help="device id (last path segment)")
    p.set_defaults(func=cmd_device)

    p = sub.add_parser("execute", help="execute a trait command on a device "
                                       "(confirmation-gated by risk grade)")
    p.add_argument("--id", required=True, help="device id (last path segment)")
    p.add_argument("--command", required=True,
                   help="e.g. ThermostatMode.SetMode, "
                        "ThermostatTemperatureSetpoint.SetHeat, "
                        "ThermostatTemperatureSetpoint.SetCool, "
                        "CameraLiveStream.GenerateRtspStream "
                        "(sdm.devices.commands. prefix optional)")
    p.add_argument("--param", action="append", default=[],
                   help="KEY=VALUE param (repeatable; JSON-parsed). SetMode: "
                        "--param mode=HEAT. SetHeat/SetCool: "
                        "--param celsius=21.5")
    p.add_argument("--confirm",
                   help="REQUIRED for thermostat commands on first use per "
                        "device. Must name the exact physical effect, e.g. "
                        "--confirm \"set the upstairs Nest to heat 21.5 degrees\".")
    p.set_defaults(func=cmd_execute)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
