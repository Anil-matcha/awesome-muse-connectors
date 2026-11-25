#!/usr/bin/env python3
"""Minimal Philips Hue CLIP v2 CLI for the muse-connectors philips-hue skill.

Auth: the bridge host comes from the runtime `--host` flag (local-network
bridge IP, https). The per-user `custom.philips-hue` credential is loaded as a
surrogate via the bundled dynamic_credentials helper and sent in the
`hue-application-key` header (n8n-style custom header). The real key never
touches this script: the runtime swaps the surrogate on approved egress, only
to the host you declared with --host.

Local API only works when this machine is on the same LAN as the bridge.
For off-network control, connect via the Hue Remote OAuth API instead (the
base becomes the remote host; the CLI contract is the same).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.philips-hue"
AUTH_HEADER = "hue-application-key"

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


def base_and_hosts(host: str) -> tuple[str, tuple[str, ...]]:
    if not (host.startswith("http://") or host.startswith("https://")):
        sys.exit("error: --host must start with http:// or https://")
    host = host.rstrip("/")
    parsed = urllib.parse.urlparse(host)
    if not parsed.hostname:
        sys.exit("error: --host must include a hostname, e.g. https://192.168.1.50")
    return host + "/clip/v2", (parsed.hostname,)


def call(host: str, method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    base, hosts = base_and_hosts(host)
    url = base + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    ensure_allowed_url(url, allowed_hosts=hosts)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        surrogate = dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    req.add_header(AUTH_HEADER, surrogate)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            errors = body.get("errors", [])
            msg = errors[0].get("description", str(exc)) if errors else str(exc)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: hue returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def first_data(result: dict) -> list:
    return result.get("data", [])


def hex_to_xy(hexcolor: str) -> tuple[float, float]:
    h = hexcolor.lstrip("#")
    if len(h) != 6:
        sys.exit("error: --color must be a hex color like #ff8800")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def gamma(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = gamma(r), gamma(g), gamma(b)
    x_cap = r * 0.664511 + g * 0.154324 + b * 0.162028
    y_cap = r * 0.283881 + g * 0.668433 + b * 0.047685
    z_cap = r * 0.000088 + g * 0.072310 + b * 0.986039
    total = x_cap + y_cap + z_cap
    if total == 0:
        return (0.0, 0.0)
    return (round(x_cap / total, 4), round(y_cap / total, 4))


def cmd_auth(args):
    result = call(args.host, "GET", "/resource/light")
    print(json.dumps({"ok": True, "lights": len(first_data(result))}, indent=2))


def cmd_lights(args):
    result = call(args.host, "GET", "/resource/light")
    lights = [
        {"id": l["id"], "name": (l.get("metadata") or {}).get("name"),
         "on": (l.get("on") or {}).get("on"),
         "brightness": (l.get("dimming") or {}).get("brightness")}
        for l in first_data(result)
    ]
    print(json.dumps(lights, indent=2))


def cmd_light_set(args):
    payload: dict = {}
    if args.on is not None:
        payload["on"] = {"on": args.on == "on"}
    if args.brightness is not None:
        if not 0 <= args.brightness <= 100:
            sys.exit("error: --brightness must be 0-100")
        payload["dimming"] = {"brightness": args.brightness}
    if args.color:
        x, y = hex_to_xy(args.color)
        payload["color"] = {"xy": {"x": x, "y": y}}
    if not payload:
        sys.exit("error: nothing to set; pass --on, --brightness, or --color")
    result = call(args.host, "PUT", f"/resource/light/{args.light_id}",
                  payload=payload)
    print(json.dumps({"ok": True, "id": args.light_id,
                      "result": first_data(result)}, indent=2))


def cmd_rooms(args):
    result = call(args.host, "GET", "/resource/room")
    rooms = [
        {"id": r["id"], "name": (r.get("metadata") or {}).get("name")}
        for r in first_data(result)
    ]
    print(json.dumps(rooms, indent=2))


def cmd_grouped_light_set(args):
    payload: dict = {}
    if args.on is not None:
        payload["on"] = {"on": args.on == "on"}
    if args.brightness is not None:
        if not 0 <= args.brightness <= 100:
            sys.exit("error: --brightness must be 0-100")
        payload["dimming"] = {"brightness": args.brightness}
    if args.color:
        x, y = hex_to_xy(args.color)
        payload["color"] = {"xy": {"x": x, "y": y}}
    if not payload:
        sys.exit("error: nothing to set; pass --on, --brightness, or --color")
    result = call(args.host, "PUT",
                  f"/resource/grouped_light/{args.grouped_light_id}",
                  payload=payload)
    print(json.dumps({"ok": True, "id": args.grouped_light_id,
                      "result": first_data(result)}, indent=2))


def cmd_scene_recall(args):
    result = call(args.host, "PUT", f"/resource/scene/{args.scene_id}",
                  payload={"recall": {"action": "active"}})
    print(json.dumps({"ok": True, "id": args.scene_id,
                      "result": first_data(result)}, indent=2))


def cmd_sensors(args):
    types = ("motion", "temperature", "light_level") if args.type == "all" \
        else (args.type,)
    out = {}
    for t in types:
        result = call(args.host, "GET", f"/resource/{t}")
        out[t] = [
            {"id": s["id"],
             "name": (s.get("metadata") or {}).get("name"),
             "owner": ((s.get("owner") or {}).get("rid"))}
            for s in first_data(result)
        ]
    print(json.dumps(out, indent=2))


def add_set_args(p):
    p.add_argument("--on", choices=("on", "off"), default=None)
    p.add_argument("--brightness", type=float, default=None,
                   help="0-100")
    p.add_argument("--color", default=None,
                   help="hex color, e.g. #ff8800")


def main():
    parser = argparse.ArgumentParser(
        description="Philips Hue CLIP v2 CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_host(p):
        p.add_argument("--host", required=True,
                       help="bridge base URL, e.g. https://192.168.1.50")

    p = sub.add_parser("auth", help="verify the bridge key")
    add_host(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("lights", help="list lights and state")
    add_host(p)
    p.set_defaults(func=cmd_lights)

    p = sub.add_parser("light-set", help="set a light (confirm first)")
    add_host(p)
    p.add_argument("--light-id", required=True)
    add_set_args(p)
    p.set_defaults(func=cmd_light_set)

    p = sub.add_parser("rooms", help="list rooms")
    add_host(p)
    p.set_defaults(func=cmd_rooms)

    p = sub.add_parser("grouped-light-set", help="set a room's grouped light (confirm first)")
    add_host(p)
    p.add_argument("--grouped-light-id", required=True,
                   help="grouped_light resource ID for the room")
    add_set_args(p)
    p.set_defaults(func=cmd_grouped_light_set)

    p = sub.add_parser("scene-recall", help="activate a scene (confirm first)")
    add_host(p)
    p.add_argument("--scene-id", required=True)
    p.set_defaults(func=cmd_scene_recall)

    p = sub.add_parser("sensors", help="read motion/temperature/light sensors")
    add_host(p)
    p.add_argument("--type", default="all",
                   choices=("all", "motion", "temperature", "light_level"))
    p.set_defaults(func=cmd_sensors)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
