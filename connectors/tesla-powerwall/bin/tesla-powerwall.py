#!/usr/bin/env python3
"""Minimal Tesla Fleet API (energy devices) CLI for the muse-connectors
tesla-powerwall skill.

Auth: loads the per-user `custom.tesla-powerwall` OAuth token as a surrogate
via the bundled dynamic_credentials helper (same OAuth pattern as the slack
and x connectors). The real token never touches this script: the runtime swaps
the surrogate on approved egress, only to the regional Tesla Fleet API host.

MEDIUM actuations (backup reserve, operation mode, storm mode) require
--confirm "<exact physical effect>" on first use per site; the confirmation
is recorded locally and later runs proceed without asking again.
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
CREDENTIAL_NAME = "custom.tesla-powerwall"
PROVIDER_ID = "tesla-powerwall"
REGION_HOSTS = {
    "na": "fleet-api.prd.na.vn.cloud.tesla.com",
    "eu": "fleet-api.prd.eu.vn.cloud.tesla.com",
    "cn": "fleet-api.prd.cn.vn.cloud.tesla.com",
}
CONFIRM_FILE = os.path.expanduser(
    "~/.cache/muse-connectors/tesla-powerwall/confirmed.json"
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
        f"'{PROVIDER_ID}' (Tesla Fleet API OAuth, scopes openid, offline_access, "
        f"energy_device_data, energy_cmds) and store the token as "
        f"{CREDENTIAL_NAME}, then re-run."
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


def require_medium_confirm(device: str, action: str, effect: str,
                           confirm: str | None) -> None:
    """MEDIUM actuation: confirm naming the exact effect on first use per device."""
    key = f"{device}:{action}"
    if key in _load_confirmed():
        return
    if confirm != effect:
        sys.exit(
            f"error: this is a MEDIUM actuation ({effect}).\n"
            f"First use on this site requires --confirm \"{effect}\".\n"
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
    result = call(args.region, "GET", "/api/1/energy_sites")
    sites = (result.get("response") or {}).get("energy_sites", [])
    print(json.dumps({"ok": True, "provider": PROVIDER_ID,
                      "energy_sites": len(sites)}, indent=2))


def cmd_sites(args):
    result = call(args.region, "GET", "/api/1/energy_sites")
    sites = (result.get("response") or {}).get("energy_sites", [])
    print(json.dumps([
        {"energy_site_id": s.get("energy_site_id"),
         "site_name": s.get("site_name"),
         "resource_type": s.get("resource_type")}
        for s in sites
    ], indent=2))


def cmd_status(args):
    result = call(args.region, "GET",
                  f"/api/1/energy_sites/{args.site_id}/live_status")
    r = result.get("response", {})
    print(json.dumps({
        "solar_power": r.get("solar_power"),
        "energy_left": r.get("energy_left"),
        "total_pack_energy": r.get("total_pack_energy"),
        "percentage_charged": r.get("percentage_charged"),
        "battery_power": r.get("battery_power"),
        "load_power": r.get("load_power"),
        "grid_power": r.get("grid_power"),
        "grid_status": r.get("grid_status"),
        "island_status": r.get("island_status"),
        "storm_mode_enabled": r.get("storm_mode_enabled"),
        "timestamp": r.get("timestamp"),
    }, indent=2))


def cmd_site_info(args):
    result = call(args.region, "GET",
                  f"/api/1/energy_sites/{args.site_id}/site_info")
    r = result.get("response", {})
    print(json.dumps({
        "site_name": r.get("site_name"),
        "backup_reserve_percent": r.get("backup_reserve_percent"),
        "default_real_mode": r.get("default_real_mode"),
        "installation_date": r.get("installation_date"),
        "installation_time_zone": r.get("installation_time_zone"),
        "nameplate_power": r.get("nameplate_power"),
        "nameplate_energy": r.get("nameplate_energy"),
        "components": r.get("components", {}),
    }, indent=2))


def cmd_history(args):
    params = {"kind": args.kind, "period": args.period}
    if args.start_date:
        params["start_date"] = args.start_date
    if args.end_date:
        params["end_date"] = args.end_date
    if args.time_zone:
        params["time_zone"] = args.time_zone
    result = call(args.region, "GET",
                  f"/api/1/energy_sites/{args.site_id}/calendar_history",
                  params=params)
    print(json.dumps(result.get("response", {}), indent=2))


def cmd_set_reserve(args):
    if not 0 <= args.percent <= 100:
        sys.exit("error: --percent must be between 0 and 100")
    effect = f"set backup reserve to {args.percent}% on site {args.site_id}"
    require_medium_confirm(args.site_id, "set-reserve", effect, args.confirm)
    result = call(args.region, "POST",
                  f"/api/1/energy_sites/{args.site_id}/backup",
                  payload={"backup_reserve_percent": args.percent})
    print(json.dumps({"ok": True, "effect": effect,
                      "response": result.get("response", {})}, indent=2))


def cmd_set_mode(args):
    effect = f"set operation mode to {args.mode} on site {args.site_id}"
    require_medium_confirm(args.site_id, "set-mode", effect, args.confirm)
    result = call(args.region, "POST",
                  f"/api/1/energy_sites/{args.site_id}/operation",
                  payload={"default_real_mode": args.mode})
    print(json.dumps({"ok": True, "effect": effect,
                      "response": result.get("response", {})}, indent=2))


def cmd_storm_mode(args):
    action = "enable" if args.enable else "disable"
    effect = f"{action} storm watch on site {args.site_id}"
    require_medium_confirm(args.site_id, "storm-mode", effect, args.confirm)
    result = call(args.region, "POST",
                  f"/api/1/energy_sites/{args.site_id}/storm_mode",
                  payload={"enabled": args.enable})
    print(json.dumps({"ok": True, "effect": effect,
                      "response": result.get("response", {})}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Tesla Fleet API energy CLI (muse-connectors)")
    parser.add_argument("--region", choices=sorted(REGION_HOSTS), default="na",
                        help="Tesla API region (default: na)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the OAuth token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("sites", help="list energy sites")
    p.set_defaults(func=cmd_sites)

    p = sub.add_parser("status", help="live power status of a site")
    p.add_argument("--site-id", required=True, help="energy_site_id")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("site-info", help="site info and settings")
    p.add_argument("--site-id", required=True, help="energy_site_id")
    p.set_defaults(func=cmd_site_info)

    p = sub.add_parser("history", help="energy/backup history")
    p.add_argument("--site-id", required=True, help="energy_site_id")
    p.add_argument("--kind", default="energy",
                   help="history kind (energy, backup, ...)")
    p.add_argument("--period", default="day", help="aggregation period")
    p.add_argument("--start-date", help="e.g. 2026-09-01T00:00:00-07:00")
    p.add_argument("--end-date", help="e.g. 2026-09-16T00:00:00-07:00")
    p.add_argument("--time-zone", help="e.g. America/Los_Angeles")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("set-reserve",
                       help="set backup reserve percent (MEDIUM: confirm first use)")
    p.add_argument("--site-id", required=True, help="energy_site_id")
    p.add_argument("--percent", type=int, required=True,
                   help="backup reserve percent, 0-100")
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "set backup reserve to 20% on site 123"')
    p.set_defaults(func=cmd_set_reserve)

    p = sub.add_parser("set-mode",
                       help="set operation mode (MEDIUM: confirm first use)")
    p.add_argument("--site-id", required=True, help="energy_site_id")
    p.add_argument("--mode", required=True,
                   choices=["self_consumption", "backup", "autonomous"],
                   help="self_consumption=self-powered, backup=backup-only, autonomous=time-based control")
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "set operation mode to self_consumption on site 123"')
    p.set_defaults(func=cmd_set_mode)

    p = sub.add_parser("storm-mode",
                       help="enable/disable storm watch (MEDIUM: confirm first use)")
    p.add_argument("--site-id", required=True, help="energy_site_id")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--enable", action="store_true")
    group.add_argument("--disable", action="store_true")
    p.add_argument("--confirm", default=None,
                   help='exact effect text, e.g. --confirm "enable storm watch on site 123"')
    p.set_defaults(func=cmd_storm_mode)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
