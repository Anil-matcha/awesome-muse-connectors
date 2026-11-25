#!/usr/bin/env python3
"""Minimal Smartcar API CLI for the muse-connectors smartcar skill.

Auth: loads the per-user `custom.smartcar` OAuth token as a surrogate via the
bundled dynamic_credentials helper (same OAuth pattern as the slack and x
connectors). The real token never touches this script: the runtime swaps the
surrogate on approved egress, only to api.smartcar.com.

Confirmation rules:
- HIGH (security LOCK/UNLOCK): --confirm "<exact physical effect>" required
  on EVERY call.
- MEDIUM (charge start/stop, charge limit, charge schedules): --confirm
  "<exact physical effect>" on first use per vehicle, then proceed.
- LOW (navigation destination, reads): no confirmation.
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
CREDENTIAL_NAME = "custom.smartcar"
PROVIDER_ID = "smartcar"
API = "https://api.smartcar.com"
ALLOWED_HOSTS = ("api.smartcar.com",)
CONFIRM_FILE = os.path.expanduser(
    "~/.cache/muse-connectors/smartcar/confirmed.json"
)

TELEMETRY = ("odometer", "location", "charge", "battery", "fuel", "tires")

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
        f"no credential stored as {CREDENTIAL_NAME}. Connect it first: register "
        f"an app at dashboard.smartcar.com, run the secure credential flow "
        f"(credentials.request_api_access) for provider '{PROVIDER_ID}' "
        f"(Smartcar Connect OAuth), and store the token as {CREDENTIAL_NAME}, "
        f"then re-run."
    )


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {"Smartcar-API-Version": "v2.0"}
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
        sys.exit(f"error: smartcar returned HTTP {exc.code}: {msg}")
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

def cmd_auth(_args):
    if not credential_available():
        print(json.dumps({
            "ok": False, "connected": False, "provider": PROVIDER_ID,
            "connect": connect_guidance(),
        }, indent=2))
        return
    result = call("GET", "/v2.0/vehicles")
    vehicles = result.get("vehicles", [])
    print(json.dumps({"ok": True, "provider": PROVIDER_ID,
                      "vehicles": len(vehicles)}, indent=2))


def cmd_vehicles(_args):
    result = call("GET", "/v2.0/vehicles")
    print(json.dumps(result.get("vehicles", []), indent=2))


def cmd_telemetry(args):
    result = call("GET", f"/v2.0/vehicles/{args.vehicle_id}/{args.metric}")
    print(json.dumps(result, indent=2))


def cmd_security(args):
    effect = ("lock the vehicle doors"
              if args.action == "LOCK" else "unlock the vehicle doors")
    require_high_confirm(effect, args.confirm)
    result = call("POST", f"/v2.0/vehicles/{args.vehicle_id}/security",
                  payload={"action": args.action})
    print(json.dumps({"ok": True, "vehicle_id": args.vehicle_id,
                      "action": args.action, "effect": effect,
                      "status": result.get("status")}, indent=2))


def cmd_charge(args):
    effect = ("start EV charging"
              if args.action == "START" else "stop EV charging")
    require_medium_confirm(args.vehicle_id, "charge", effect, args.confirm)
    result = call("POST", f"/v2.0/vehicles/{args.vehicle_id}/charge",
                  payload={"action": args.action})
    print(json.dumps({"ok": True, "vehicle_id": args.vehicle_id,
                      "action": args.action, "effect": effect,
                      "status": result.get("status")}, indent=2))


def cmd_charge_limit(args):
    if not 0 < args.limit <= 100:
        sys.exit("error: --limit must be between 1 and 100")
    effect = f"set the charge limit to {args.limit}%"
    require_medium_confirm(args.vehicle_id, "charge-limit", effect,
                           args.confirm)
    result = call("POST",
                  f"/v2.0/vehicles/{args.vehicle_id}/charge-limit",
                  payload={"limit": args.limit})
    print(json.dumps({"ok": True, "vehicle_id": args.vehicle_id,
                      "limit": args.limit, "effect": effect}, indent=2))


def cmd_navigate(args):
    result = call("POST",
                  f"/v2.0/vehicles/{args.vehicle_id}/navigation/destination",
                  payload={"latitude": args.lat, "longitude": args.lon})
    print(json.dumps({"ok": True, "vehicle_id": args.vehicle_id,
                      "destination": {"latitude": args.lat,
                                      "longitude": args.lon}}, indent=2))


def cmd_charge_schedules(args):
    try:
        schedules = json.loads(args.schedules)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --schedules is not valid JSON: {exc}")
    effect = "replace the vehicle's charge schedules"
    require_medium_confirm(args.vehicle_id, "charge-schedules", effect,
                           args.confirm)
    result = call("POST",
                  f"/v2.0/vehicles/{args.vehicle_id}/charge-schedules",
                  payload=schedules)
    print(json.dumps({"ok": True, "vehicle_id": args.vehicle_id,
                      "effect": effect, "response": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Smartcar API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the OAuth token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("vehicles", help="list connected vehicles")
    p.set_defaults(func=cmd_vehicles)

    p = sub.add_parser("telemetry", help="read one telemetry metric")
    p.add_argument("--vehicle-id", required=True)
    p.add_argument("--metric", required=True, choices=TELEMETRY,
                   help="odometer, location, charge, battery, fuel, tires")
    p.set_defaults(func=cmd_telemetry)

    p = sub.add_parser("security",
                       help="LOCK/UNLOCK all doors (HIGH: always confirm)")
    p.add_argument("--vehicle-id", required=True)
    p.add_argument("--action", required=True, choices=["LOCK", "UNLOCK"])
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "unlock the vehicle doors"')
    p.set_defaults(func=cmd_security)

    p = sub.add_parser("charge",
                       help="START/STOP EV charging (MEDIUM: confirm first use)")
    p.add_argument("--vehicle-id", required=True)
    p.add_argument("--action", required=True, choices=["START", "STOP"])
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "start EV charging"')
    p.set_defaults(func=cmd_charge)

    p = sub.add_parser("charge-limit",
                       help="set max charge percent (MEDIUM: confirm first use)")
    p.add_argument("--vehicle-id", required=True)
    p.add_argument("--limit", type=int, required=True,
                   help="charge limit percent, 1-100")
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "set the charge limit to 80%"')
    p.set_defaults(func=cmd_charge_limit)

    p = sub.add_parser("navigate",
                       help="route the car's navigation to a destination (LOW)")
    p.add_argument("--vehicle-id", required=True)
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.set_defaults(func=cmd_navigate)

    p = sub.add_parser("charge-schedules",
                       help="set charge time windows (MEDIUM: confirm first use)")
    p.add_argument("--vehicle-id", required=True)
    p.add_argument("--schedules", required=True,
                   help="charge schedules as a JSON object per the Smartcar docs")
    p.add_argument("--confirm", default=None,
                   help='--confirm "replace the vehicle\'s charge schedules"')
    p.set_defaults(func=cmd_charge_schedules)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
