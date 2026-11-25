#!/usr/bin/env python3
"""Minimal Rachio sprinkler API CLI for the muse-connectors rachio skill.

Auth: loads the per-user `custom.rachio` personal API key as a surrogate via
the bundled dynamic_credentials helper. Rachio authenticates with
`Authorization: Bearer <token>`; the placement is resolved by the helper from
the credential config. The real key never touches this script: the runtime
swaps the surrogate on approved egress, only to api.rach.io.

Safety: `zone-start` opens a real valve (water flows) and requires an exact
--confirm string echoed by the CLI. `stop` closes all valves and never
requires confirmation.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.rachio"
ALLOWED_HOSTS = ("api.rach.io",)
API = "https://api.rach.io"
CONNECT_GUIDANCE = (
    "not connected: collect a Rachio personal API key (Rachio app -> Account "
    "settings -> API keys) via the secure credential flow "
    "(credentials.request_api_access) as `custom.rachio`, then retry."
)

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
    except DynamicCredentialError as exc:
        if "missing" in str(exc) or "surrogate" in str(exc):
            sys.exit(CONNECT_GUIDANCE)
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: rachio returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def cmd_auth(_args):
    result = call("GET", "/1/public/person/info")
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "username": result.get("username"),
                      "full_name": result.get("fullName")}, indent=2))


def cmd_person(_args):
    result = call("GET", "/1/public/person/info")
    devices = [{"id": d.get("id"), "name": d.get("name"),
                "status": d.get("status")}
               for d in result.get("devices", [])]
    print(json.dumps({"id": result.get("id"),
                      "username": result.get("username"),
                      "email": result.get("email"),
                      "devices": devices}, indent=2))


def cmd_schedule(args):
    result = call("GET", f"/1/public/device/{args.device_id}/current_schedule")
    print(json.dumps(result, indent=2))


def cmd_zone_start(args):
    expected = f"water zone {args.zone_id} for {args.seconds} seconds"
    need_confirm(args, expected, "zone-start opens a valve: water will flow.")
    result = call("PUT", "/1/public/zone/start",
                  {"id": args.zone_id, "duration": args.seconds})
    print(json.dumps({"ok": True, "zone_id": args.zone_id,
                      "seconds": args.seconds, "result": result}, indent=2))


def cmd_stop(args):
    person_id = args.person_id
    if not person_id:
        person = call("GET", "/1/public/person/info")
        person_id = person.get("id")
        if not person_id:
            sys.exit("error: could not resolve the person id")
    call("PUT", "/1/public/device/stop_water", {"id": person_id})
    print(json.dumps({"ok": True, "water_stopped": True}, indent=2))


def cmd_device_on(args):
    expected = f"enable controller {args.device_id}"
    need_confirm(args, expected, "this enables the controller (watering can run).")
    call("PUT", "/1/public/device/on", {"id": args.device_id})
    print(json.dumps({"ok": True, "device_id": args.device_id,
                      "enabled": True}, indent=2))


def cmd_device_off(args):
    expected = f"disable controller {args.device_id}"
    need_confirm(args, expected, "this disables the controller.")
    call("PUT", "/1/public/device/off", {"id": args.device_id})
    print(json.dumps({"ok": True, "device_id": args.device_id,
                      "enabled": False}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Rachio sprinkler API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("person", help="person info and controller ids")
    p.set_defaults(func=cmd_person)

    p = sub.add_parser("schedule", help="current schedule on a controller")
    p.add_argument("--device-id", required=True, help="controller device id")
    p.set_defaults(func=cmd_schedule)

    p = sub.add_parser("zone-start", help="open a zone valve for N seconds (water flows)")
    p.add_argument("--zone-id", required=True)
    p.add_argument("--seconds", type=int, required=True,
                   help="how long the valve stays open")
    p.add_argument("--confirm", default=None,
                   help="exact confirmation string echoed by the CLI on refusal")
    p.set_defaults(func=cmd_zone_start)

    p = sub.add_parser("stop", help="emergency off: close all valves")
    p.add_argument("--person-id", default=None,
                   help="defaults to the authenticated person")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("device-on", help="enable a controller")
    p.add_argument("--device-id", required=True)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_device_on)

    p = sub.add_parser("device-off", help="disable a controller")
    p.add_argument("--device-id", required=True)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_device_off)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
