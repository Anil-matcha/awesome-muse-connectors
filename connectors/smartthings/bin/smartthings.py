#!/usr/bin/env python3
"""SmartThings REST API CLI (production version).

Auth: the per-user `custom.smartthings` credential, loaded as a surrogate via
the bundled dynamic_credentials helper. The real token never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.smartthings.com.

Usage:
  smartthings.py auth                     status check: list locations
  smartthings.py devices                  list all devices (id, label, type)
  smartthings.py device <deviceId>        device details
  smartthings.py status <deviceId>        live capability states
  smartthings.py command <deviceId> <capability> <command> [args-json]
             [--component <name>] [--arg <json>]... [--confirm <effect>]
                                          execute a device command, e.g.
                                          smartthings.py command <id> switch on
                                          smartthings.py command <id> switchLevel setLevel '[80]'
                                          smartthings.py command <id> switchLevel setLevel --arg 80
                                          Arguments come from [args-json] OR
                                          repeatable --arg (each JSON-parsed),
                                          never both. --component defaults to
                                          "main". Actuation gating:
                                          HIGH (lock capability; doorControl /
                                          garageDoorControl open|close) refuses
                                          unless --confirm exactly equals
                                          "<capability>:<command>:<deviceId>",
                                          on every run. MEDIUM (all other
                                          commands) needs --confirm on first
                                          use; the confirmation is remembered
                                          bound to device+component+capability
                                          +command+args for 30 days.
  smartthings.py scenes                   list scenes
  smartthings.py scene <sceneId> [--confirm <effect>]
                                          execute a scene (MEDIUM gate)
  smartthings.py history [locationId] [--device <deviceId>] [--limit N]
                                          location device-event history
  smartthings.py health <deviceId>        device health (ONLINE/OFFLINE)
  smartthings.py mqtt-broker [locationId] MQTT broker URL for a location
  smartthings.py locations                list locations
  smartthings.py rooms <locationId>       list rooms in a location
  smartthings.py modes <locationId>       list location modes
  smartthings.py mode-current <locationId>
                                          get current location mode
  smartthings.py mode-set <locationId> <modeId|name> [--confirm <effect>]
                                          set location mode (MEDIUM gate)
  smartthings.py vswitch <name> <roomId> [locationId] [--confirm <effect>]
                                          create a cloud virtual switch
                                          (MEDIUM gate)
  smartthings.py delete <deviceId> [--confirm <effect>]
                                          delete a device (MEDIUM gate; the
                                          confirmation binds to the device id)

Where a locationId is optional, it defaults to the account's first location.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import (  # noqa: E402
    add_surrogate_to_request,
    read_json_response,
    DynamicCredentialError,
)

BASE = "https://api.smartthings.com/v1"
CREDENTIAL = "custom.smartthings"
ALLOWED = ["api.smartthings.com"]
CONFIRM_FILE = os.path.expanduser(
    "~/.config/muse-connectors/smartthings/confirmed.json")
CONFIRM_TTL_DAYS = 30

HIGH_CAPS_EXACT = {"lock"}                       # any command
HIGH_CAPS_CMDS = {"doorControl", "garageDoorControl"}
HIGH_CMDS = {"open", "close"}


# ---------------------------------------------------------------------------
# Confirmation gating (hardened)
# ---------------------------------------------------------------------------

def _load_records() -> list:
    try:
        with open(CONFIRM_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_records(records: list) -> None:
    os.makedirs(os.path.dirname(CONFIRM_FILE), exist_ok=True)
    with open(CONFIRM_FILE, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2)


def _args_hash(args) -> str:
    canon = json.dumps(args, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def require_high(confirm, capability, command, device_id):
    """HIGH actuations: exact-effect --confirm, every single run, never
    remembered. The confirm value must be exactly
    '<capability>:<command>:<deviceId>'."""
    expected = f"{capability}:{command}:{device_id}"
    if confirm != expected:
        raise SystemExit(
            f"refused: {capability} {command} on device {device_id} is "
            f"HIGH-risk; re-run with --confirm '{expected}' (the exact "
            f"effect, confirmed by the user in conversation, every run)")
    print(f"notice: HIGH actuation confirmed: {expected}", file=sys.stderr)


def require_medium(confirm, key, args, effect):
    """MEDIUM actuations: --confirm on first use. A confirmation is
    remembered only bound to (key + args hash) and expires after
    CONFIRM_TTL_DAYS days; a different target or different arguments
    needs a fresh confirmation."""
    ah = _args_hash(args)
    now = time.time()
    records = [r for r in _load_records() if r.get("expires_at", 0) > now]
    for r in records:
        if r.get("key") == key and r.get("args_hash") == ah:
            print(f"notice: MEDIUM actuation previously confirmed for {key} "
                  f"(expires in {int((r['expires_at'] - now) / 86400)}d)",
                  file=sys.stderr)
            return
    if not confirm or len(confirm.strip()) < 3:
        raise SystemExit(
            f"refused: first use of this MEDIUM actuation needs confirmation. "
            f"This would: {effect}. Re-run with --confirm '<exact effect>' "
            f"after the user confirms in conversation; it will be remembered "
            f"for this exact target+arguments for {CONFIRM_TTL_DAYS} days.")
    records.append({"key": key, "args_hash": ah,
                    "expires_at": now + CONFIRM_TTL_DAYS * 86400,
                    "effect": confirm.strip()})
    _save_records(records)
    print(f"notice: MEDIUM actuation confirmed and recorded for {key}",
          file=sys.stderr)


def low_notice(effect):
    print(f"notice: LOW actuation proceeding: {effect}", file=sys.stderr)


def is_high(capability, command):
    return capability in HIGH_CAPS_EXACT or (
        capability in HIGH_CAPS_CMDS and command in HIGH_CMDS)


# ---------------------------------------------------------------------------
# API plumbing
# ---------------------------------------------------------------------------

def call(method, path, body=None):
    url = BASE + path if path.startswith("/") else path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=ALLOWED)
    except DynamicCredentialError as exc:
        raise SystemExit(
            f"not connected: no custom.smartthings credential is stored ({exc}). "
            "Collect it via the secure credential flow "
            "(credentials.request_api_access); see SKILL.md Auth.")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 204:
                return {}
            return read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            detail = ""
        raise SystemExit(f"HTTP {e.code}: {detail}")


def first_location_id():
    items = call("GET", "/locations").get("items", [])
    if not items:
        raise SystemExit("no locations on this SmartThings account")
    return items[0]["locationId"]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_auth():
    items = call("GET", "/locations").get("items", [])
    print(json.dumps({"ok": True, "locations": [
        {"name": loc.get("name"), "locationId": loc.get("locationId")}
        for loc in items]}, indent=2))


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]

    # split off --confirm <value> from the tail args where supported
    def take_confirm(args):
        out, confirm, i = [], None, 0
        while i < len(args):
            if args[i] == "--confirm" and i + 1 < len(args):
                confirm = args[i + 1]
                i += 2
            else:
                out.append(args[i])
                i += 1
        return out, confirm

    if cmd == "auth":
        cmd_auth()
        return 0
    elif cmd == "devices":
        out = call("GET", "/devices")
    elif cmd == "device" and len(rest) == 1:
        out = call("GET", f"/devices/{rest[0]}")
    elif cmd == "status" and len(rest) == 1:
        out = call("GET", f"/devices/{rest[0]}/status")
    elif cmd == "command" and len(rest) >= 3:
        device_id, capability, command = rest[0], rest[1], rest[2]
        extra = rest[3:]
        component = "main"
        confirm = None
        cli_args = []
        positional_json = None
        i = 0
        while i < len(extra):
            tok = extra[i]
            if tok == "--component" and i + 1 < len(extra):
                component = extra[i + 1]
                i += 2
            elif tok == "--arg" and i + 1 < len(extra):
                try:
                    cli_args.append(json.loads(extra[i + 1]))
                except json.JSONDecodeError:
                    raise SystemExit(f"command: --arg value is not valid JSON: {extra[i + 1]}")
                i += 2
            elif tok == "--confirm" and i + 1 < len(extra):
                confirm = extra[i + 1]
                i += 2
            elif positional_json is None:
                positional_json = tok
                i += 1
            else:
                raise SystemExit(f"command: unexpected argument {tok}")
        if positional_json is not None and cli_args:
            raise SystemExit("command: pass arguments via [args-json] or --arg, not both")
        if cli_args:
            args = cli_args
        elif positional_json is not None:
            args = json.loads(positional_json)
        else:
            args = []
        effect = f"send {capability}.{command} {args} to device {device_id} (component {component})"
        if is_high(capability, command):
            require_high(confirm, capability, command, device_id)
        elif capability in ("windowShade", "windowShadeLevel", "windowShadePreset"):
            low_notice(effect)
        else:
            require_medium(confirm,
                           f"device:{device_id}:{component}:{capability}:{command}",
                           args, effect)
        out = call("POST", f"/devices/{device_id}/commands", {
            "commands": [{
                "component": component,
                "capability": capability,
                "command": command,
                "arguments": args,
            }]
        })
    elif cmd == "health" and len(rest) == 1:
        out = call("GET", f"/devices/{rest[0]}/health")
    elif cmd == "mqtt-broker" and len(rest) <= 1:
        location_id = rest[0] if rest else first_location_id()
        # App-surface endpoint on the public host without the /v1 prefix:
        # GET https://api.smartthings.com/mqtt/broker/{locationId} returns an
        # ssl:// broker URL. Connecting additionally needs MQTT client auth.
        out = call("GET", f"https://api.smartthings.com/mqtt/broker/{location_id}")
    elif cmd == "history":
        location_id = None
        device_id, limit = None, 20
        args = list(rest)
        if args and not args[0].startswith("--"):
            location_id = args.pop(0)
        while args:
            flag = args.pop(0)
            if flag == "--device" and args:
                device_id = args.pop(0)
            elif flag == "--limit" and args:
                limit = int(args.pop(0))
            else:
                raise SystemExit(f"history: unknown argument {flag}")
        if not location_id:
            location_id = first_location_id()
        path = f"/history/devices?locationId={location_id}&limit={limit}"
        if device_id:
            path += f"&deviceId={device_id}"
        out = call("GET", path)
    elif cmd == "scenes":
        out = call("GET", "/scenes")
    elif cmd == "scene" and rest:
        rest, confirm = take_confirm(rest)
        if len(rest) != 1:
            print(__doc__)
            return 2
        require_medium(confirm, f"scene:{rest[0]}", [],
                       f"execute scene {rest[0]}")
        out = call("POST", f"/scenes/{rest[0]}/execute", {})
    elif cmd == "locations":
        out = call("GET", "/locations")
    elif cmd == "rooms" and len(rest) == 1:
        out = call("GET", f"/locations/{rest[0]}/rooms")
    elif cmd == "modes" and len(rest) == 1:
        out = call("GET", f"/locations/{rest[0]}/modes")
    elif cmd == "mode-current" and len(rest) == 1:
        out = call("GET", f"/locations/{rest[0]}/modes/current")
    elif cmd == "mode-set" and rest:
        rest, confirm = take_confirm(rest)
        if len(rest) != 2:
            print(__doc__)
            return 2
        location_id, mode_ref = rest[0], rest[1]
        modes = call("GET", f"/locations/{location_id}/modes").get("items", [])
        mode_id = None
        for m in modes:
            if (m.get("id") == mode_ref
                    or m.get("name", "").lower() == mode_ref.lower()
                    or m.get("label", "").lower() == mode_ref.lower()):
                mode_id = m["id"]
                break
        if not mode_id:
            raise SystemExit(f"mode not found: {mode_ref}")
        require_medium(confirm, f"mode:{location_id}:{mode_id}", [],
                       f"set location mode to {mode_ref}")
        out = call("PUT", f"/locations/{location_id}/modes/current",
                   {"modeId": mode_id})
    elif cmd == "delete" and rest:
        rest, confirm = take_confirm(rest)
        if len(rest) != 1:
            print(__doc__)
            return 2
        require_medium(confirm, f"delete:{rest[0]}", [],
                       f"DELETE device {rest[0]}")
        out = call("DELETE", f"/devices/{rest[0]}")
        print(f"deleted {rest[0]}")
        return 0
    elif cmd == "vswitch" and rest:
        rest, confirm = take_confirm(rest)
        if len(rest) not in (2, 3):
            print(__doc__)
            return 2
        name, room_id = rest[0], rest[1]
        location_id = rest[2] if len(rest) == 3 else first_location_id()
        require_medium(confirm, f"vswitch:{name}:{room_id}", [],
                       f"create cloud virtual switch '{name}'")
        # POST /v1/virtualdevices/prototypes (NOT /v1/virtualdevices — that
        # path 422s). Cloud switches omit hubId.
        out = call("POST", "/virtualdevices/prototypes", {
            "name": name,
            "roomId": room_id,
            "prototype": "VIRTUAL_SWITCH",
            "executionTarget": "CLOUD",
            "owner": {"ownerType": "LOCATION", "ownerId": location_id},
        })
    else:
        print(__doc__)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
