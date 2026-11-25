#!/usr/bin/env python3
"""Minimal Homey Web API CLI for the muse-connectors skill.

Auth: personal API token (Homey Pro) or OAuth 2.0 token (Homey cloud),
stored as the per-user `custom.homey` credential and loaded as a surrogate
via the bundled dynamic_credentials helper, sent as
`Authorization: Bearer <token>`. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to the --host given
at runtime.

--host is required on every run: the API root, either local
(http://<homey-ip>/api) or cloud (https://<cloud-id>.connect.athom.com/api).

Physical-world safety: lock capability writes are HIGH and require
--confirm "<exact physical effect>" on every run. Other capability writes
(onoff, dim, thermostat) are MEDIUM: first use per device needs --confirm,
then proceeds (confirmations recorded locally). Blind/curtain capability
writes are LOW: they proceed with a logged notice. Flow triggering is an
open item: its path is UNTESTED (see below) and HIGH-gated per flow.
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
CREDENTIAL_NAME = "custom.homey"
CONFIRM_FILE = os.path.expanduser("~/.config/muse-connectors/homey/confirmed.json")
# Open item: the exact Flow-trigger path could not be pinned from public docs.
FLOW_TRIGGER_PATH_TEMPLATE = "/manager/flow/flow/{id}/trigger"  # UNTESTED

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


def low_notice(effect: str) -> None:
    print(f"notice: LOW actuation proceeding: {effect}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Auth + API plumbing
# ---------------------------------------------------------------------------

def base_url(args) -> str:
    host = args.host.rstrip("/")
    if not (host.startswith("http://") or host.startswith("https://")):
        sys.exit("error: --host must start with http:// or https:// "
                 "and include /api, e.g. http://192.168.1.60/api")
    return host


def token() -> str:
    try:
        return str(dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]).strip()
    except DynamicCredentialError:
        print(
            "not connected: no custom.homey credential is stored.\n"
            "Collect it via the secure credential flow "
            "(credentials.request_api_access) as a Homey personal API token "
            "(Homey Pro) or an OAuth 2.0 token (Homey cloud), then retry. "
            "See this skill's SKILL.md Auth section.",
            file=sys.stderr,
        )
        sys.exit(1)


def call(args, method: str, path: str, payload: dict | None = None) -> dict:
    base = base_url(args)
    url = base + path
    allowed = (urllib.parse.urlparse(base).hostname,)
    ensure_allowed_url(url, allowed_hosts=allowed)
    data = None
    headers = {"Authorization": f"Bearer {token()}"}
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
        sys.exit(f"error: homey returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def parse_value(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_auth(args):
    devices = call(args, "GET", "/manager/devices/device")
    count = len(devices) if isinstance(devices, dict) else 0
    print(json.dumps({"ok": True, "host": base_url(args),
                      "devices": count}, indent=2))


def cmd_devices(args):
    devices = call(args, "GET", "/manager/devices/device")
    if isinstance(devices, dict):
        out = [{"id": did, "name": d.get("name"),
                "capabilities": sorted((d.get("capabilitiesObj") or {}).keys())}
               for did, d in devices.items()]
    else:
        out = devices
    print(json.dumps(out, indent=2))


def cmd_device(args):
    result = call(args, "GET", f"/manager/devices/device/{args.id}")
    print(json.dumps(result, indent=2))


def cmd_set(args):
    cap = args.cap
    value = parse_value(args.value)

    # --- actuation-risk grading ---
    if cap == "locked":
        require_high(args.confirm,
                     f"{'lock' if value else 'unlock'} the Homey-connected "
                     f"lock device {args.id}")
    elif cap in ("windowcoverings_state", "windowcoverings_set"):
        low_notice(f"move the blinds/curtains on Homey device {args.id} "
                   f"({cap} = {value})")
    else:
        require_medium(args.id, cap, args.confirm,
                       f"set capability '{cap}' = {args.value} on Homey "
                       f"device {args.id}")

    result = call(args, "PUT", f"/manager/devices/device/{args.id}",
                  {cap: value})
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_flows(args):
    result = call(args, "GET", "/manager/flow/flow")
    if isinstance(result, dict):
        out = [{"id": fid, "name": f.get("name"),
                "enabled": f.get("enabled"), "trigger": bool(f.get("trigger"))}
               for fid, f in result.items()]
    else:
        out = result
    print(json.dumps(out, indent=2))


def cmd_flow_trigger(args):
    # UNTESTED path (open item): verify against Athom docs on first live use.
    require_high(args.confirm,
                 f"trigger Homey Flow {args.id} (its physical effects are "
                 "whatever that Flow's actions do)")
    print("warning: the Flow-trigger path is UNTESTED in this connector; "
          "verify it against Athom's docs on first live use.",
          file=sys.stderr)
    path = FLOW_TRIGGER_PATH_TEMPLATE.format(
        id=urllib.parse.quote(args.id, safe=""))
    result = call(args, "POST", path, {})
    print(json.dumps({"ok": True, "result": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Homey Web API CLI (muse-connectors). --host is the API "
                    "root: http://<homey-ip>/api (Pro, local) or "
                    "https://<cloud-id>.connect.athom.com/api (cloud). Lock "
                    "writes are HIGH and always need --confirm; other "
                    "capability writes need --confirm on first use per "
                    "device; blind/curtain writes proceed with a notice. "
                    "Flow triggering ships with an UNTESTED path.")
    parser.add_argument("--host", required=True,
                        help="Homey API root, e.g. http://192.168.1.60/api")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="status check: list devices, verify token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("devices", help="list devices with capabilities")
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("device", help="device detail")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_device)

    p = sub.add_parser("set", help="set a capability value on a device "
                                   "(confirmation-gated by risk grade)")
    p.add_argument("--id", required=True, help="device id")
    p.add_argument("--cap", required=True,
                   help="capability, e.g. onoff, dim, locked, "
                        "target_temperature, thermostat_mode, "
                        "windowcoverings_state, light_hue")
    p.add_argument("--value", required=True,
                   help="value (JSON-parsed: true, 0.5, 21.5, '\"heat\"')")
    p.add_argument("--confirm",
                   help="REQUIRED for lock writes (locked true/false) on every "
                        "run, and for other capabilities on first use per "
                        "device. Must name the exact physical effect, e.g. "
                        "--confirm \"unlock the side door\".")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("flows", help="list Flows (automations)")
    p.set_defaults(func=cmd_flows)

    p = sub.add_parser("flow-trigger", help="UNTESTED path: trigger a Flow "
                                            "(HIGH: always needs --confirm; "
                                            "the Flow's effects are whatever "
                                            "its actions do)")
    p.add_argument("--id", required=True, help="flow id")
    p.add_argument("--confirm",
                   help="REQUIRED: name the Flow's physical effect.")
    p.set_defaults(func=cmd_flow_trigger)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
