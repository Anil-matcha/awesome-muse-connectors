#!/usr/bin/env python3
"""Minimal Ecovacs Open Platform CLI for the muse-connectors ecovacs skill.

Auth: the self-serve Access Key (AK) from the Open Platform console
(https://open.ecovacs.com, or https://open.ecovacs.cn for mainland China) is
stored as the `custom.ecovacs` credential and passed as the `?ak=` query
parameter on every request, per Ecovacs' vendor-published Deebot skill
reference (GET /robot/skill/deviceList?ak=...; control via
POST /robot/skill/ctl with the AK in the JSON body). This CLI attaches the AK
as a query parameter on the request URL for both reads and control calls;
the AK value itself never appears on the command line, in the environment,
or in a file.

Discovery and control use the documented gateway paths only
(/robot/skill/deviceList, /robot/skill/ctl); no vendor-internal hosts or
app-layer login flows are used.

Confirmation rules:
- MEDIUM (clean start): --confirm "start cleaning on <robot>" on first use
  per robot, then proceed.
- LOW (pause, resume, stop, dock return, work-mode set, reads): no
  confirmation.
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
CREDENTIAL_NAME = "custom.ecovacs"
PROVIDER_ID = "ecovacs"
REGION_HOSTS = {
    "global": "open.ecovacs.com",
    "cn": "open.ecovacs.cn",
}
CONFIRM_FILE = os.path.expanduser(
    "~/.cache/muse-connectors/ecovacs/confirmed.json"
)

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        dynamic_credential_entry,
        read_json_response,
        url_with_surrogate_query_param,
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
        f"no credential stored as {CREDENTIAL_NAME}. Create an Access Key in "
        f"the Ecovacs Open Platform console (Service overview) at "
        f"https://open.ecovacs.com (global) or https://open.ecovacs.cn "
        f"(mainland China), using the same regional portal as your account "
        f"and robots, then run the secure credential flow "
        f"(credentials.request_api_access) for provider '{PROVIDER_ID}' and "
        f"store the AK as {CREDENTIAL_NAME} (query-param placement on `ak`), "
        f"then re-run."
    )


def authed_url(region: str, path: str) -> str:
    """Attach the AK surrogate as ?ak= on the request URL."""
    base = "https://" + REGION_HOSTS[region] + path
    try:
        return url_with_surrogate_query_param(
            base, CREDENTIAL_NAME,
            allowed_hosts=tuple(REGION_HOSTS.values()))
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}\n{connect_guidance()}")


def call(region: str, method: str, path: str,
         payload: dict | None = None) -> dict:
    url = authed_url(region, path)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("msg", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: ecovacs returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if result.get("code") not in (0, None):
        sys.exit(f"error: ecovacs error {result.get('code')}: "
                 f"{result.get('msg')}")
    return result


def ctl(region: str, robot: str, cmd: str, data: dict) -> dict:
    """POST /robot/skill/ctl with a CloudCtl command."""
    body = {"nickName": robot, "ctl": {"cmd": cmd, "data": data}}
    result = call(region, "POST", "/robot/skill/ctl", payload=body)
    inner = (((result.get("data") or {}).get("ctl") or {}).get("data")
             if isinstance(result.get("data"), dict) else None)
    out = {"ok": True, "cmd": cmd, "data": result.get("data")}
    if isinstance(inner, dict) and inner.get("ret") not in (None, "ok"):
        out["warning"] = (f"device returned ret={inner.get('ret')} "
                          f"errno={inner.get('errno')}")
    return out


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


def require_medium_confirm(robot: str, action: str, effect: str,
                           confirm: str | None) -> None:
    key = f"{robot}:{action}"
    if key in _load_confirmed():
        return
    if confirm != effect:
        sys.exit(
            f"error: this is a MEDIUM actuation ({effect}).\n"
            f"First use on this robot requires --confirm \"{effect}\".\n"
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
    result = call(args.region, "GET", "/robot/skill/deviceList")
    devices = result.get("data", [])
    print(json.dumps({"ok": True, "provider": PROVIDER_ID,
                      "devices": len(devices)}, indent=2))


def cmd_devices(args):
    result = call(args.region, "GET", "/robot/skill/deviceList")
    devices = result.get("data", [])
    print(json.dumps([
        {"nick": d.get("nick"), "name": d.get("name"),
         "deviceName": d.get("deviceName"), "status": d.get("status")}
        for d in devices
    ], indent=2))


def cmd_status(args):
    result = ctl(args.region, args.robot, "GetWorkState", {})
    data = result.get("data") or {}
    robot_state = data.get("robotState", {})
    print(json.dumps({
        "paused": data.get("paused"),
        "state": robot_state.get("state"),
        "trigger": robot_state.get("trigger"),
        "clean_type": (robot_state.get("cleanState") or {}).get("type"),
        "station_state": (data.get("stationState") or {}).get("state"),
    }, indent=2))


def cmd_battery(args):
    result = ctl(args.region, args.robot, "GetBatteryInfo", {})
    data = result.get("data") or {}
    level = data.get("value", data.get("power"))
    print(json.dumps({"battery_percent": level,
                      "is_low": data.get("isLow")}, indent=2))


def cmd_stats(args):
    result = ctl(args.region, args.robot, "GetStats", {})
    data = result.get("data") or {}
    print(json.dumps({"area_m2": data.get("area"),
                      "time_s": data.get("time"),
                      "type": data.get("type")}, indent=2))


def cmd_clean(args):
    effect = f"start cleaning on {args.robot}"
    require_medium_confirm(args.robot, "clean", effect, args.confirm)
    result = ctl(args.region, args.robot, "Clean",
                 {"act": "s", "type": "auto", "workMode": 0})
    result["effect"] = effect
    print(json.dumps(result, indent=2))


def _simple_ctl(args, cmd: str, data: dict, effect: str):
    result = ctl(args.region, args.robot, cmd, data)
    result["effect"] = effect
    print(json.dumps(result, indent=2))


def cmd_pause(args):
    _simple_ctl(args, "Clean", {"act": "p"}, f"pause cleaning on {args.robot}")


def cmd_resume(args):
    _simple_ctl(args, "Clean", {"act": "r"},
                f"resume cleaning on {args.robot}")


def cmd_stop(args):
    _simple_ctl(args, "Clean", {"act": "h"}, f"stop cleaning on {args.robot}")


def cmd_dock(args):
    _simple_ctl(args, "Charge", {"act": "go"},
                f"send {args.robot} back to the charging dock")


def cmd_undock(args):
    _simple_ctl(args, "Charge", {"act": "stopGo"},
                f"stop {args.robot} returning to the dock")


def cmd_set_work_mode(args):
    modes = {0: "sweep+mop", 1: "sweep only", 2: "mop only",
             3: "sweep then mop"}
    result = ctl(args.region, args.robot, "SetWorkMode",
                 {"noVoiceResp": 1, "mode": args.mode})
    result["effect"] = f"set work mode to {modes[args.mode]} on {args.robot}"
    print(json.dumps(result, indent=2))


def add_region(p):
    p.add_argument("--region", choices=sorted(REGION_HOSTS), default="global",
                   help="Open Platform region: global (open.ecovacs.com) or "
                        "cn (open.ecovacs.cn). Must match the account region.")


def add_robot(p):
    p.add_argument("--robot", required=True,
                   help="robot nickname (a fragment of the name in the app)")


def main():
    parser = argparse.ArgumentParser(
        description="Ecovacs Open Platform CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the Access Key")
    add_region(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("devices", help="list bound robots")
    add_region(p)
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("status", help="robot state (cleaning, paused, docked...)")
    add_region(p); add_robot(p)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("battery", help="battery level")
    add_region(p); add_robot(p)
    p.set_defaults(func=cmd_battery)

    p = sub.add_parser("stats", help="area cleaned and duration")
    add_region(p); add_robot(p)
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("clean",
                       help="start a whole-home clean (MEDIUM: confirm first use)")
    add_region(p); add_robot(p)
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "start cleaning on Blue"')
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("pause", help="pause cleaning (LOW)")
    add_region(p); add_robot(p)
    p.set_defaults(func=cmd_pause)

    p = sub.add_parser("resume", help="resume cleaning (LOW)")
    add_region(p); add_robot(p)
    p.set_defaults(func=cmd_resume)

    p = sub.add_parser("stop", help="stop cleaning (LOW)")
    add_region(p); add_robot(p)
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("dock", help="return to the charging dock (LOW)")
    add_region(p); add_robot(p)
    p.set_defaults(func=cmd_dock)

    p = sub.add_parser("undock", help="stop returning to the dock (LOW)")
    add_region(p); add_robot(p)
    p.set_defaults(func=cmd_undock)

    p = sub.add_parser("set-work-mode",
                       help="set sweep/mop work mode (LOW)")
    add_region(p); add_robot(p)
    p.add_argument("--mode", type=int, required=True, choices=[0, 1, 2, 3],
                   help="0=sweep+mop, 1=sweep only, 2=mop only, 3=sweep then mop")
    p.set_defaults(func=cmd_set_work_mode)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
