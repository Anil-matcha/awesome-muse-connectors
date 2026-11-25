#!/usr/bin/env python3
"""Minimal Tuya Cloud API CLI for the muse-connectors skill.

Auth: the per-user `custom.tuya` credential stores ONE combined value
"access_id:access_secret" (langfuse precedent). The CLI splits it, fetches a
cloud token via GET /v1.0/token?grant_type=1, then signs every request per the
Tuya HMAC-SHA256 scheme (client_id + access_token + t + nonce + stringToSign).
The real secrets never touch this script: the runtime swaps the surrogate on
approved egress, only to the regional openapi host.

Physical-world safety: smart-lock commands and scene executions are HIGH and
require --confirm "<exact physical effect>" on every run. Other commands
(relays, HVAC, curtains) are MEDIUM: first use per device needs --confirm,
then proceeds (confirmations recorded locally).

Honesty note: the request signature is computed over the credential surrogate
value, exactly as received from the credential store. Whether the runtime's
egress substitution keeps signed headers valid must be verified in a live
test before first signed use. Draft, untested.
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
CREDENTIAL_NAME = "custom.tuya"
ALLOWED_HOSTS = (
    "openapi.tuyaus.com",
    "openapi-ueaz.tuyaus.com",
    "openapi.tuyaeu.com",
    "openapi-weaz.tuyaeu.com",
    "openapi.tuyacn.com",
    "openapi.tuyain.com",
)
REGIONS = {
    "us": "openapi.tuyaus.com",
    "eu": "openapi.tuyaeu.com",
    "cn": "openapi.tuyacn.com",
    "in": "openapi.tuyain.com",
}
CONFIRM_FILE = os.path.expanduser("~/.config/muse-connectors/tuya/confirmed.json")

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
# Auth: split combined credential, sign requests per Tuya's scheme
# ---------------------------------------------------------------------------

def credentials():
    try:
        surrogate = dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]
    except DynamicCredentialError:
        print(
            "not connected: no custom.tuya credential is stored.\n"
            "Collect it via the secure credential flow "
            "(credentials.request_api_access) as ONE combined value "
            "\"access_id:access_secret\" from your Tuya IoT Platform project "
            "(Access ID + Access Secret), then retry. "
            "See this skill's SKILL.md Auth section.",
            file=sys.stderr,
        )
        sys.exit(1)
    surrogate = str(surrogate).strip()
    if ":" not in surrogate:
        sys.exit("error: credential must be in 'access_id:access_secret' format")
    access_id, _, access_secret = surrogate.partition(":")
    return access_id.strip(), access_secret.strip()


def sign_request(access_id: str, access_secret: str, method: str, url: str,
                 access_token: str, body: bytes | None) -> dict:
    t = str(int(time.time() * 1000))
    nonce = uuid.uuid4().hex
    parsed = urllib.parse.urlparse(url)
    path = parsed.path + ("?" + parsed.query if parsed.query else "")
    body_hash = hashlib.sha256(body or b"").hexdigest()
    string_to_sign = f"{method}\n{body_hash}\n\n{path}"
    str_to_sign = access_id + access_token + t + nonce + string_to_sign
    sign = hmac.new(access_secret.encode("utf-8"),
                    str_to_sign.encode("utf-8"),
                    hashlib.sha256).hexdigest().upper()
    return {
        "client_id": access_id,
        "access_token": access_token,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
        "nonce": nonce,
        "Content-Type": "application/json",
    }


def call(host: str, method: str, path: str, payload: dict | None = None,
         access_token: str = "") -> dict:
    access_id, access_secret = credentials()
    url = f"https://{host}{path}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    headers = sign_request(access_id, access_secret, method, url, access_token,
                           data)
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            result = json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("msg", body.get("message", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: tuya returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if not result.get("success", False):
        sys.exit(f"error: tuya API error: {result.get('msg')} "
                 f"(code {result.get('code')})")
    return result


def get_token(host: str) -> str:
    result = call(host, "GET", "/v1.0/token?grant_type=1")
    token = result.get("result", {}).get("access_token")
    if not token:
        sys.exit("error: tuya did not return an access_token")
    return token


def authed_call(args, method: str, path: str, payload: dict | None = None) -> dict:
    host = REGIONS[args.region]
    token = get_token(host)
    return call(host, method, path, payload, access_token=token)


def parse_value(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_auth(args):
    host = REGIONS[args.region]
    token = get_token(host)
    print(json.dumps({"ok": True, "region": args.region, "host": host,
                      "token_type": "bearer",
                      "token_prefix": token[:6] + "..."}, indent=2))


def cmd_device(args):
    result = authed_call(args, "GET", f"/v1.0/devices/{args.id}")
    print(json.dumps(result.get("result", {}), indent=2))


def cmd_status(args):
    result = authed_call(args, "GET", f"/v1.0/iot-03/devices/{args.id}/status")
    print(json.dumps(result.get("result", {}), indent=2))


def cmd_command(args):
    code = args.code
    value = parse_value(args.value)
    if "lock" in code.lower():
        require_high(args.confirm,
                     f"operate the smart lock data point '{code}' on device {args.id}")
    else:
        require_medium(args.id, "command", args.confirm,
                       f"send data point '{code}' = {args.value} to device {args.id}")
    payload = {"commands": [{"code": code, "value": value}]}
    result = authed_call(args, "POST",
                         f"/v1.0/iot-03/devices/{args.id}/commands", payload)
    print(json.dumps({"ok": True, "result": result.get("result")}, indent=2))


def cmd_scene(args):
    # NOTE (open item): the scene-trigger path form below follows Tuya's public
    # docs but is UNTESTED in this connector. It ships HIGH-gated; verify the
    # path on first live use before trusting it.
    require_high(args.confirm,
                 f"execute Tuya scene {args.scene} in home {args.home} "
                 "(its physical effects are whatever that scene was saved with)")
    result = authed_call(args, "POST",
                         f"/v1.0/homes/{args.home}/scenes/{args.scene}/trigger")
    print(json.dumps({"ok": True, "result": result.get("result")}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Tuya Cloud API CLI (muse-connectors). --region must match "
                    "the account region. Smart-lock commands and scene "
                    "executions are HIGH and always need --confirm; other "
                    "commands need --confirm on first use per device.")
    parser.add_argument("--region", default="us", choices=sorted(REGIONS),
                        help="account region: us, eu, cn, in (default us)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="status check: fetch a cloud token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("device", help="read device information")
    p.add_argument("--id", required=True, help="device id")
    p.set_defaults(func=cmd_device)

    p = sub.add_parser("status", help="read device data-point status")
    p.add_argument("--id", required=True, help="device id")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("command", help="send a control command to a device "
                                       "(confirmation-gated by risk grade)")
    p.add_argument("--id", required=True, help="device id")
    p.add_argument("--code", required=True,
                   help="data point code, e.g. switch_1, temp_set, lock_motor_state")
    p.add_argument("--value", required=True,
                   help="value (JSON-parsed: true, 24, '\"off\"')")
    p.add_argument("--confirm",
                   help="REQUIRED for smart-lock data points on every run, "
                        "and for other commands on first use per device. Must "
                        "name the exact physical effect, e.g. --confirm "
                        "\"unlock the side door smart lock\".")
    p.set_defaults(func=cmd_command)

    p = sub.add_parser("scene", help="UNTESTED path: execute a saved scene "
                                     "(HIGH: always needs --confirm; the "
                                     "scene's effects are whatever was saved "
                                     "into it)")
    p.add_argument("--home", required=True, help="home id")
    p.add_argument("--scene", required=True, help="scene id")
    p.add_argument("--confirm", required=False,
                   help="REQUIRED: name the scene's physical effect, e.g. "
                        "--confirm \"run the Goodnight scene (locks doors, "
                        "turns off lights)\".")
    p.set_defaults(func=cmd_scene)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
