#!/usr/bin/env python3
"""Minimal Aqara Open Cloud API CLI for the muse-connectors skill.

Auth: OAuth-style account authorization; the access token is stored as the
per-user `custom.aqara` credential and loaded as a surrogate via the bundled
dynamic_credentials helper, sent as `Authorization: Bearer <token>`. The real
token never touches this script: the runtime swaps the surrogate on approved
egress, only to the regional open-<region>.aqara.com host.

OPEN ITEMS (do not trust these calls until a live verification pass):
  1. Aqara's exact REST path form and request-signature headers could not be
     pinned from public docs at build time. Every command below is marked
     UNTESTED in its help text. The CLI posts the dossier's intent names
     (get_homes, get_home_devices, device_control, ...) as the request `type`
     in Aqara's documented envelope style
     {"type","version":"v1","msgId","data"} to the regional host path
     /v3.0/open/api. If the official OpenAPI reference uses different paths
     or a signature scheme, these calls must be repointed at connect time.
  2. Aqara also documents a request-signature scheme (per-account signing on
     top of the bearer token); its exact headers are unresolved, so this CLI
     sends the bearer token only.

Physical-world safety: lock endpoints are HIGH and require
--confirm "<exact physical effect>" on every run. Plug/switch toggles and AC
changes are MEDIUM: first use per device needs --confirm, then proceeds
(confirmations recorded locally). Light/curtain changes are LOW: they proceed
with a logged notice. Scenes are HIGH per-scene.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.aqara"
CONFIRM_FILE = os.path.expanduser("~/.config/muse-connectors/aqara/confirmed.json")

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
# Auth + API plumbing (UNTESTED transport; see module docstring)
# ---------------------------------------------------------------------------

def bearer_token() -> str:
    try:
        return str(dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]).strip()
    except DynamicCredentialError:
        print(
            "not connected: no custom.aqara credential is stored.\n"
            "Collect it via the secure credential flow "
            "(credentials.request_api_access) as the Aqara OAuth access token "
            "(complete the account authorization flow at developer.aqara.com, "
            "then store the access token), then retry. "
            "See this skill's SKILL.md Auth section.",
            file=sys.stderr,
        )
        sys.exit(1)


def host_for(region: str) -> str:
    return f"https://open-{region}.aqara.com"


def call(region: str, intent: str, data: dict | None = None) -> dict:
    """UNTESTED: posts the dossier's intent name as the request `type`."""
    host = host_for(region)
    url = host + "/v3.0/open/api"  # UNTESTED path; see module docstring
    allowed = (urllib.parse.urlparse(host).hostname,)
    ensure_allowed_url(url, allowed_hosts=allowed)
    envelope = {
        "type": intent,
        "version": "v1",
        "msgId": f"msg-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}",
        "data": data or {},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(envelope).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {bearer_token()}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: aqara returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if isinstance(result, dict) and result.get("code") not in (None, 0):
        sys.exit(f"error: aqara API error {result.get('code')}: "
                 f"{result.get('message')}")
    return result


def parse_value(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text


# ---------------------------------------------------------------------------
# Commands (every one marked UNTESTED until a live verification pass)
# ---------------------------------------------------------------------------

def cmd_auth(args):
    result = call(args.region, "get_homes")
    data = result.get("data", result)
    homes = data.get("homes", []) if isinstance(data, dict) else []
    print(json.dumps({"ok": True, "region": args.region, "homes": homes},
                     indent=2))


def cmd_homes(args):
    result = call(args.region, "get_homes")
    print(json.dumps(result.get("data", result), indent=2))


def cmd_rooms(args):
    result = call(args.region, "get_rooms", {"home_id": args.home})
    print(json.dumps(result.get("data", result), indent=2))


def cmd_devices(args):
    result = call(args.region, "get_home_devices", {"home_id": args.home})
    print(json.dumps(result.get("data", result), indent=2))


def cmd_status(args):
    result = call(args.region, "post_device_status",
                  {"device_id": args.device})
    print(json.dumps(result.get("data", result), indent=2))


def cmd_control(args):
    action = args.action
    attribute = args.attribute
    value = parse_value(args.value) if args.value is not None else None
    endpoint_ids = [int(e) for e in args.endpoint.split(",")]

    # --- actuation-risk grading ---
    if "lock" in attribute.lower() or "lock" in action.lower():
        require_high(args.confirm,
                     f"operate the lock endpoint(s) {endpoint_ids} on Aqara "
                     f"device {args.device} ({action} {attribute})")
    elif attribute.lower() in ("brightness", "color_temperature",
                               "color", "on_off") and action in ("set",):
        low_notice(f"change light output on Aqara device {args.device} "
                   f"({attribute} = {value})")
    elif attribute.lower() in ("curtain", "window_covering") or action in ("up", "down", "stop"):
        low_notice(f"move the curtain on Aqara device {args.device} ({action})")
    else:
        require_medium(args.device, "device_control", args.confirm,
                       f"device_control {action} {attribute} = {value} on "
                       f"Aqara device {args.device}")

    control_params = {"action": action, "attribute": attribute}
    if value is not None:
        control_params["value"] = value
    if args.unit:
        control_params["unit"] = args.unit
    result = call(args.region, "device_control",
                  {"endpoint_ids": endpoint_ids, "control_params": control_params,
                   "device_id": args.device})
    print(json.dumps({"ok": True, "data": result.get("data", result)}, indent=2))


def cmd_scenes(args):
    result = call(args.region, "get_scenes", {"home_id": args.home})
    print(json.dumps(result.get("data", result), indent=2))


def cmd_run_scene(args):
    require_high(args.confirm,
                 f"execute Aqara scene {args.scene} in home {args.home} (its "
                 "physical effects are whatever that scene was saved with)")
    result = call(args.region, "run_scenes",
                  {"home_id": args.home, "scene_id": args.scene})
    print(json.dumps({"ok": True, "data": result.get("data", result)}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Aqara Open Cloud API CLI (muse-connectors). EVERY path "
                    "is UNTESTED: exact REST paths and signature headers could "
                    "not be pinned from public docs at build time. Verify "
                    "against the official OpenAPI reference on first live "
                    "use. --region picks the regional host "
                    "(open-<region>.aqara.com).")
    parser.add_argument("--region", default="us",
                        help="account region, e.g. us, eu, cn (default us)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="UNTESTED: status check, list homes")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("homes", help="UNTESTED: list homes")
    p.set_defaults(func=cmd_homes)

    p = sub.add_parser("rooms", help="UNTESTED: list rooms in a home")
    p.add_argument("--home", required=True, help="home id")
    p.set_defaults(func=cmd_rooms)

    p = sub.add_parser("devices", help="UNTESTED: list devices in a home")
    p.add_argument("--home", required=True, help="home id")
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("status", help="UNTESTED: read device attributes")
    p.add_argument("--device", required=True, help="device id")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("control", help="UNTESTED: immediate device control "
                                       "(confirmation-gated by risk grade)")
    p.add_argument("--device", required=True, help="device id")
    p.add_argument("--endpoint", default="1",
                   help="endpoint id(s), comma-separated (default 1)")
    p.add_argument("--action", required=True,
                   help="on, off, set, up, down, stop")
    p.add_argument("--attribute", required=True,
                   help="on_off, brightness, color_temperature, ac_mode, "
                        "lock attributes, ...")
    p.add_argument("--value", default=None,
                   help="target value (JSON-parsed; required with --action set)")
    p.add_argument("--unit", default=None, help="unit, e.g. %%, K")
    p.add_argument("--confirm",
                   help="REQUIRED for lock endpoints on every run, and for "
                        "other controls on first use per device. Must name "
                        "the exact physical effect.")
    p.set_defaults(func=cmd_control)

    p = sub.add_parser("scenes", help="UNTESTED: list scenes in a home")
    p.add_argument("--home", required=True, help="home id")
    p.set_defaults(func=cmd_scenes)

    p = sub.add_parser("run-scene", help="UNTESTED: execute a scene (HIGH: "
                                         "always needs --confirm)")
    p.add_argument("--home", required=True, help="home id")
    p.add_argument("--scene", required=True, help="scene id")
    p.add_argument("--confirm",
                   help="REQUIRED: name the scene's physical effect.")
    p.set_defaults(func=cmd_run_scene)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
