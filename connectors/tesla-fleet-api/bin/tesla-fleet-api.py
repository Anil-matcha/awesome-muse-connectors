#!/usr/bin/env python3
"""Minimal Tesla Fleet API (vehicles) CLI for the muse-connectors
tesla-fleet-api skill.

Auth: loads the per-user `custom.tesla-fleet-api` OAuth token as a surrogate
via the bundled dynamic_credentials helper (same OAuth pattern as the slack
and x connectors). The real token never touches this script: the runtime swaps
the surrogate on approved egress, only to the regional Tesla Fleet API host.

Commands go through POST /api/1/vehicles/{vehicle}/signed_command; the payload
selects the action. Signed commands only work after the developer app's public
key is hosted on a verified domain AND the vehicle has paired the app's
virtual key. The signed_command envelope below follows the official Fleet API
reference and is untested in this build.

Confirmation rules:
- HIGH (door_lock, door_unlock, remote_start_drive): --confirm "<exact
  physical effect>" is required on EVERY call.
- MEDIUM (charge start/stop/limit, sentry/valet/speed-limit): --confirm
  "<exact physical effect>" on first use per vehicle, then proceed.
- LOW (honk, flash, trunk, preconditioning, navigation, software-update
  scheduling): no confirmation.
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
CREDENTIAL_NAME = "custom.tesla-fleet-api"
PROVIDER_ID = "tesla-fleet-api"
REGION_HOSTS = {
    "na": "fleet-api.prd.na.vn.cloud.tesla.com",
    "eu": "fleet-api.prd.eu.vn.cloud.tesla.com",
    "cn": "fleet-api.prd.cn.vn.cloud.tesla.com",
}
CONFIRM_FILE = os.path.expanduser(
    "~/.cache/muse-connectors/tesla-fleet-api/confirmed.json"
)

# Actuation grades per the official Fleet API command surface.
HIGH_ACTIONS = {"door_lock", "door_unlock", "remote_start_drive"}
MEDIUM_ACTIONS = {
    "charge_start", "charge_stop", "set_charge_limit",
    "set_sentry_mode", "set_valet_mode",
    "speed_limit_activate", "speed_limit_set_limit",
}
LOW_ACTIONS = {
    "honk_horn", "flash_lights", "actuate_trunk",
    "auto_conditioning_start", "auto_conditioning_stop",
    "navigation_gps_request", "schedule_software_update",
}

EFFECT_TEXT = {
    "door_lock": "lock all vehicle doors",
    "door_unlock": "unlock all vehicle doors",
    "remote_start_drive": "enable keyless driving for 2 minutes",
    "charge_start": "start EV charging",
    "charge_stop": "stop EV charging",
    "set_charge_limit": "change the charge limit",
    "set_sentry_mode": "change sentry mode",
    "set_valet_mode": "change valet mode",
    "speed_limit_activate": "activate the speed limit",
    "speed_limit_set_limit": "change the speed limit",
    "honk_horn": "honk the horn",
    "flash_lights": "flash the lights",
    "actuate_trunk": "actuate the trunk/frunk",
    "auto_conditioning_start": "start cabin preconditioning",
    "auto_conditioning_stop": "stop cabin preconditioning",
    "navigation_gps_request": "send a navigation destination to the car",
    "schedule_software_update": "schedule a software update",
}

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
        f"no credential stored as {CREDENTIAL_NAME}. Connect it first: run the "
        f"secure credential flow (credentials.request_api_access) for provider "
        f"'{PROVIDER_ID}' (Tesla Fleet API OAuth third-party tokens; scopes "
        f"openid, offline_access, vehicle_device_data, vehicle_cmds, "
        f"vehicle_charging_cmds, vehicle_location) and store the token as "
        f"{CREDENTIAL_NAME}, then re-run. Signed commands additionally need the "
        f"app's public key on a verified domain and the vehicle to pair the "
        f"app's virtual key."
    )


def api_host(region: str) -> str:
    return "https://" + REGION_HOSTS[region]


def call(region: str, method: str, path: str,
         params: dict | None = None, payload: dict | None = None) -> dict:
    url = api_host(region) + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(
            req, CREDENTIAL_NAME,
            allowed_hosts=tuple(REGION_HOSTS.values()),
        )
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}\n{connect_guidance()}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", body.get("message", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: tesla fleet api returned HTTP {exc.code}: {msg}")
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


def require_high_confirm(effect: str, confirm: str | None) -> None:
    if confirm != effect:
        sys.exit(
            f"error: HIGH actuation ({effect}).\n"
            f"Re-run with --confirm \"{effect}\" to confirm this exact effect."
        )


def require_medium_confirm(vehicle: str, action: str, effect: str,
                           confirm: str | None) -> None:
    key = f"{vehicle}:{action}"
    if key in _load_confirmed():
        return
    if confirm != effect:
        sys.exit(
            f"error: this is a MEDIUM actuation ({effect}).\n"
            f"First use on this vehicle requires --confirm \"{effect}\".\n"
            "After the first confirmation, later runs proceed without asking."
        )
    _record_confirmed(key)


# ---- commands ------------------------------------------------------------

def cmd_auth(args):
    if not credential_available():
        print(json.dumps({
            "ok": False, "connected": False, "provider": PROVIDER_ID,
            "connect": connect_guidance(),
        }, indent=2))
        return
    result = call(args.region, "GET", "/api/1/vehicles")
    vehicles = result.get("response", [])
    print(json.dumps({"ok": True, "provider": PROVIDER_ID,
                      "vehicles": len(vehicles)}, indent=2))


def cmd_vehicles(args):
    result = call(args.region, "GET", "/api/1/vehicles")
    vehicles = result.get("response", [])
    print(json.dumps([
        {"id": v.get("id"), "vin": v.get("vin"),
         "display_name": v.get("display_name"), "state": v.get("state")}
        for v in vehicles
    ], indent=2))


def cmd_vehicle_data(args):
    params = {}
    if args.endpoints:
        params["endpoints"] = args.endpoints
    result = call(args.region, "GET",
                  f"/api/1/vehicles/{args.vehicle}/vehicle_data",
                  params=params or None)
    print(json.dumps(result.get("response", {}), indent=2))


def cmd_wake(args):
    # LOW grade with a cost warning: waking is reversible, but wakes are
    # metered (about 50 per $1) and the car draws power while awake.
    result = call(args.region, "POST",
                  f"/api/1/vehicles/{args.vehicle}/wake_up")
    print(json.dumps({"ok": True, "vehicle": args.vehicle,
                      "state": (result.get("response") or {}).get("state")},
                     indent=2))


def cmd_command(args):
    action = args.action
    if action not in EFFECT_TEXT:
        sys.exit(f"error: unknown action {action!r}")
    effect = EFFECT_TEXT[action]
    if action in HIGH_ACTIONS:
        require_high_confirm(effect, args.confirm)
    elif action in MEDIUM_ACTIONS:
        require_medium_confirm(args.vehicle, action, effect, args.confirm)
    # else LOW: proceed
    extra = {}
    if args.params:
        try:
            extra = json.loads(args.params)
        except json.JSONDecodeError as exc:
            sys.exit(f"error: --params is not valid JSON: {exc}")
    payload = {"routineName": action, **extra}
    result = call(args.region, "POST",
                  f"/api/1/vehicles/{args.vehicle}/signed_command",
                  payload=payload)
    print(json.dumps({"ok": True, "vehicle": args.vehicle, "action": action,
                      "effect": effect,
                      "response": result.get("response", {})}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Tesla Fleet API vehicle CLI (muse-connectors)")
    parser.add_argument("--region", choices=sorted(REGION_HOSTS), default="na",
                        help="Tesla API region (default: na)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the OAuth token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("vehicles", help="list vehicles")
    p.set_defaults(func=cmd_vehicles)

    p = sub.add_parser("vehicle-data", help="read live vehicle state")
    p.add_argument("--vehicle", required=True,
                   help="vehicle tag, usually the VIN")
    p.add_argument("--endpoints", default=None,
                   help="semicolon-separated endpoints, e.g. charge_state;climate_state")
    p.set_defaults(func=cmd_vehicle_data)

    p = sub.add_parser("wake", help="wake a sleeping vehicle (metered)")
    p.add_argument("--vehicle", required=True,
                   help="vehicle tag, usually the VIN")
    p.set_defaults(func=cmd_wake)

    p = sub.add_parser("command", help="send a signed vehicle command")
    p.add_argument("--vehicle", required=True,
                   help="vehicle tag, usually the VIN")
    p.add_argument("--action", required=True,
                   choices=sorted(EFFECT_TEXT),
                   help="command to run; HIGH actions always need --confirm, "
                        "MEDIUM actions need --confirm on first use per vehicle")
    p.add_argument("--params", default=None,
                   help="extra command parameters as a JSON object, e.g. "
                        "'{\"percent\": 80}' for set_charge_limit")
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "unlock all vehicle doors"')
    p.set_defaults(func=cmd_command)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
