#!/usr/bin/env python3
"""Minimal SwitchBot OpenAPI v1.1 CLI for the muse-connectors skill.

Auth: the per-user `custom.switchbot` credential stores ONE combined value
"token:secret" (langfuse precedent) from the SwitchBot app. The CLI sends the
token in the `Authorization` header plus an HMAC-SHA256 signature of
`token + t + nonce` in the `sign` header, with `t` and `nonce` headers. The
real secrets never touch this script: the runtime swaps the surrogate on
approved egress, only to api.switch-bot.com.

Physical-world safety: lock/unlock and scene execution are HIGH and require
--confirm "<exact physical effect>" on every run. Bot presses, plug/light
toggles, and AC commands are MEDIUM: first use per device needs --confirm,
then proceeds (confirmations recorded locally). Curtain/blind moves are LOW:
they proceed with a logged notice.

Honesty note: the HMAC signature is computed over the credential surrogate
value as delivered by the credential store. Whether the runtime's egress
substitution keeps signed headers valid must be verified in a live test
before first signed use. Draft, untested.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.switchbot"
ALLOWED_HOSTS = ("api.switch-bot.com",)
API = "https://api.switch-bot.com/v1.1"
CONFIRM_FILE = os.path.expanduser("~/.config/muse-connectors/switchbot/confirmed.json")

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

def credentials():
    try:
        surrogate = dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]
    except DynamicCredentialError:
        print(
            "not connected: no custom.switchbot credential is stored.\n"
            "Collect it via the secure credential flow "
            "(credentials.request_api_access) as ONE combined value "
            "\"token:secret\" from the SwitchBot app (Profile > Preferences > "
            "App Version tap, then get the open token + secret), then retry. "
            "See this skill's SKILL.md Auth section.",
            file=sys.stderr,
        )
        sys.exit(1)
    surrogate = str(surrogate).strip()
    if ":" not in surrogate:
        sys.exit("error: credential must be in 'token:secret' format")
    token, _, secret = surrogate.partition(":")
    return token.strip(), secret.strip()


def call(method: str, path: str, payload: dict | None = None) -> dict:
    token, secret = credentials()
    t = str(int(time.time() * 1000))
    nonce = uuid.uuid4().hex
    sign = hmac.new(secret.encode("utf-8"),
                    (token + t + nonce).encode("utf-8"),
                    hashlib.sha256).hexdigest().upper()
    url = API + path
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    data = None
    headers = {
        "Authorization": token,
        "sign": sign,
        "t": t,
        "nonce": nonce,
        "Content-Type": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: switchbot returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if result.get("statusCode") != 100:
        sys.exit(f"error: switchbot API error {result.get('statusCode')}: "
                 f"{result.get('message')}")
    return result.get("body", {})


def parse_value(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_auth(_args):
    body = call("GET", "/devices")
    devices = body.get("deviceList", [])
    print(json.dumps({"ok": True,
                      "devices": len(devices),
                      "infrared_remotes": len(body.get("infraredRemoteList", []))},
                     indent=2))


def cmd_devices(_args):
    body = call("GET", "/devices")
    print(json.dumps({
        "devices": [{"deviceId": d.get("deviceId"), "deviceName": d.get("deviceName"),
                     "deviceType": d.get("deviceType"),
                     "hubDeviceId": d.get("hubDeviceId")}
                    for d in body.get("deviceList", [])],
        "infrared_remotes": [{"deviceId": d.get("deviceId"),
                              "deviceName": d.get("deviceName"),
                              "remoteType": d.get("remoteType")}
                             for d in body.get("infraredRemoteList", [])],
    }, indent=2))


def cmd_status(args):
    body = call("GET", f"/devices/{args.id}/status")
    print(json.dumps(body, indent=2))


def cmd_command(args):
    command = args.command
    if args.param:
        params = {}
        for pair in args.param:
            if "=" not in pair:
                sys.exit("error: --param must be KEY=VALUE")
            k, _, v = pair.partition("=")
            params[k] = parse_value(v)
        parameter = json.dumps(params)
    else:
        parameter = args.parameter

    # --- actuation-risk grading ---
    if command in ("lock", "unlock"):
        require_high(args.confirm,
                     f"{command} the SwitchBot Lock device {args.id}")
    elif command == "setPosition":
        low_notice(f"move the curtain/blind motors on device {args.id} "
                   f"to position {parameter}")
    else:
        require_medium(args.id, "command", args.confirm,
                       f"send '{command}' to SwitchBot device {args.id}")

    payload = {"command": command, "parameter": parameter,
               "commandType": "command"}
    body = call("POST", f"/devices/{args.id}/commands", payload)
    print(json.dumps({"ok": True, "body": body}, indent=2))


def cmd_scenes(_args):
    body = call("GET", "/scenes")
    print(json.dumps([{"sceneId": s.get("sceneId"), "sceneName": s.get("sceneName")}
                      for s in (body if isinstance(body, list) else [])], indent=2))


def cmd_scene_execute(args):
    require_high(args.confirm,
                 f"execute SwitchBot scene {args.scene_id} (its physical "
                 "effects are whatever was saved into it)")
    body = call("POST", f"/scenes/{args.scene_id}/execute")
    print(json.dumps({"ok": True, "body": body}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="SwitchBot OpenAPI v1.1 CLI (muse-connectors). lock/unlock "
                    "and scene execution are HIGH and always need --confirm; "
                    "press/toggle/AC commands need --confirm on first use per "
                    "device; curtain moves (setPosition) proceed with a notice.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="status check: list devices, verify token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("devices", help="list devices and infrared remotes")
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("status", help="read device status")
    p.add_argument("--id", required=True, help="deviceId")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("command", help="send a command to a device "
                                       "(confirmation-gated by risk grade)")
    p.add_argument("--id", required=True, help="deviceId")
    p.add_argument("--command", required=True,
                   help="e.g. turnOn, turnOff, press, lock, unlock, "
                        "setPosition, setAll, setMode")
    p.add_argument("--parameter", default="default",
                   help="raw parameter string (default 'default'; used for "
                        "press, turnOn, turnOff, lock, unlock)")
    p.add_argument("--param", action="append", default=[],
                   help="KEY=VALUE pair; when given, the parameter becomes a "
                        "JSON object of the pairs (e.g. --param position=50 "
                        "for setPosition, or AC setAll fields)")
    p.add_argument("--confirm",
                   help="REQUIRED for lock/unlock on every run, and for other "
                        "commands on first use per device. Must name the exact "
                        "physical effect, e.g. --confirm \"unlock the back "
                        "door SwitchBot lock\".")
    p.set_defaults(func=cmd_command)

    p = sub.add_parser("scenes", help="list scenes")
    p.set_defaults(func=cmd_scenes)

    p = sub.add_parser("scene-execute", help="execute a scene (HIGH: always "
                                             "needs --confirm)")
    p.add_argument("--scene-id", required=True)
    p.add_argument("--confirm",
                   help="REQUIRED: name the scene's physical effect.")
    p.set_defaults(func=cmd_scene_execute)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
