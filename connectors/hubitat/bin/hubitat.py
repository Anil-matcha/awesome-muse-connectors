#!/usr/bin/env python3
"""Minimal Hubitat Maker API CLI for the muse-connectors skill.

Auth: the per-user `custom.hubitat` credential holds the Maker API access
token. The CLI appends it as `?access_token=<token>` on every request (the
token travels in the query string; see the skill docs). The real token never
touches this script: the runtime swaps the surrogate on approved egress, only
to the --host given at runtime.

--host is required on every run: the local Maker API base URL
(http://<hub-ip>/apps/api/<app-id>) or the cloud relay URL issued by the
Maker API app.

Physical-world safety: lock/unlock and garage open/close are HIGH and require
--confirm "<exact physical effect>" on every run. Light/dimmer/HVAC commands
and HSM arm/disarm are MEDIUM: first use per device needs --confirm, then
proceeds (confirmations recorded locally).
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
CREDENTIAL_NAME = "custom.hubitat"
CONFIRM_FILE = os.path.expanduser("~/.config/muse-connectors/hubitat/confirmed.json")

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


def require_high(confirm: str | None, effect: str) -> None:
    if not confirm or len(confirm.strip()) < 3:
        sys.exit(
            "error: HIGH-RISK actuation blocked. This command would: "
            f"{effect}. Re-run with --confirm \"<exact physical effect>\" "
            f"naming it, e.g. --confirm \"{effect}\"."
        )
    print(f"notice: HIGH actuation confirmed: {confirm.strip()}", file=sys.stderr)


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


# ---------------------------------------------------------------------------
# Auth + API plumbing
# ---------------------------------------------------------------------------

def base_url(args) -> str:
    host = args.host.rstrip("/")
    if not (host.startswith("http://") or host.startswith("https://")):
        sys.exit("error: --host must start with http:// or https://")
    return host


def token() -> str:
    try:
        return str(dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]).strip()
    except DynamicCredentialError:
        print(
            "not connected: no custom.hubitat credential is stored.\n"
            "Collect it via the secure credential flow "
            "(credentials.request_api_access) as the Maker API access token "
            "(Hubitat hub > Apps > Maker API > the token shown for your app "
            "instance), then retry. See this skill's SKILL.md Auth section.",
            file=sys.stderr,
        )
        sys.exit(1)


def call(args, method: str, path: str, payload: dict | None = None) -> dict:
    base = base_url(args)
    url = base + path
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("access_token", token()))
    url = urllib.parse.urlunsplit(parsed._replace(
        query=urllib.parse.urlencode(query)))
    allowed = (urllib.parse.urlparse(base).hostname,)
    ensure_allowed_url(url, allowed_hosts=allowed)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    except urllib.error.HTTPError as exc:
        try:
            msg = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            msg = str(exc)
        sys.exit(f"error: hubitat returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_auth(args):
    devices = call(args, "GET", "/devices")
    count = len(devices) if isinstance(devices, list) else 0
    print(json.dumps({"ok": True, "host": base_url(args),
                      "devices": count}, indent=2))


def cmd_devices(args):
    devices = call(args, "GET", "/devices")
    print(json.dumps(devices, indent=2))


def cmd_device(args):
    result = call(args, "GET", f"/devices/{args.id}")
    print(json.dumps(result, indent=2))


def cmd_events(args):
    result = call(args, "GET", f"/devices/{args.id}/events")
    print(json.dumps(result, indent=2))


def cmd_command(args):
    command = args.command
    segments = "/".join(urllib.parse.quote(p, safe="") for p in args.param)

    # --- actuation-risk grading ---
    if command in ("lock", "unlock"):
        require_high(args.confirm,
                     f"{command} the deadbolt device {args.id} on the Hubitat hub")
    elif command in ("open", "close"):
        require_high(args.confirm,
                     f"{command} the garage/door device {args.id} on the Hubitat hub")
    else:
        require_medium(args.id, command, args.confirm,
                       f"send '{command}' to Hubitat device {args.id}")

    path = f"/devices/{args.id}/{command}" + (f"/{segments}" if segments else "")
    result = call(args, "GET", path)
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_modes(args):
    result = call(args, "GET", "/modes")
    print(json.dumps(result, indent=2))


def cmd_mode_set(args):
    require_medium("hub", "mode", args.confirm,
                   f"set the Hubitat location mode to id {args.id}")
    result = call(args, "PUT", f"/modes/{args.id}")
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_hsm(args):
    result = call(args, "GET", "/hsm")
    print(json.dumps(result, indent=2))


def cmd_hsm_set(args):
    require_medium("hub", "hsm", args.confirm,
                   f"set Hubitat Safety Monitor to '{args.state}' (arms or "
                   "disarms intrusion/smoke/water monitoring and siren alerts)")
    result = call(args, "PUT", f"/hsm/{args.state}")
    print(json.dumps({"ok": True, "result": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Hubitat Maker API CLI (muse-connectors). --host is the "
                    "Maker API base URL (local http://<hub-ip>/apps/api/<app-id> "
                    "or the cloud relay URL). lock/unlock and garage open/close "
                    "are HIGH and always need --confirm; other commands need "
                    "--confirm on first use per device.")
    parser.add_argument("--host", required=True,
                        help="Maker API base URL, e.g. "
                             "http://192.168.1.50/apps/api/12")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="status check: list devices, verify token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("devices", help="list devices with current attributes")
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("device", help="device detail")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_device)

    p = sub.add_parser("events", help="recent events for a device")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_events)

    p = sub.add_parser("command", help="invoke a capability command on a device "
                                       "(confirmation-gated by risk grade)")
    p.add_argument("--id", required=True, help="device id")
    p.add_argument("--command", required=True,
                   help="e.g. on, off, setLevel, lock, unlock, open, close, "
                        "setThermostatMode, setHeatingSetpoint")
    p.add_argument("--param", action="append", default=[],
                   help="secondary parameter as an extra path segment "
                        "(repeatable), e.g. --param 50 for setLevel")
    p.add_argument("--confirm",
                   help="REQUIRED for lock/unlock and garage open/close on "
                        "every run, and for other commands on first use per "
                        "device. Must name the exact physical effect, e.g. "
                        "--confirm \"unlock the front door deadbolt\".")
    p.set_defaults(func=cmd_command)

    p = sub.add_parser("modes", help="list location modes")
    p.set_defaults(func=cmd_modes)

    p = sub.add_parser("mode-set", help="set location mode (MEDIUM: first use "
                                        "needs --confirm)")
    p.add_argument("--id", required=True, help="mode id")
    p.add_argument("--confirm", help="REQUIRED on first use.")
    p.set_defaults(func=cmd_mode_set)

    p = sub.add_parser("hsm", help="read Hubitat Safety Monitor state")
    p.set_defaults(func=cmd_hsm)

    p = sub.add_parser("hsm-set", help="arm/disarm HSM (MEDIUM: first use "
                                       "needs --confirm)")
    p.add_argument("--state", required=True,
                   help="armAway, armHome, armNight, disarm, etc.")
    p.add_argument("--confirm", help="REQUIRED on first use.")
    p.set_defaults(func=cmd_hsm_set)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
