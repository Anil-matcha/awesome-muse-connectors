#!/usr/bin/env python3
"""Minimal UniFi Protect Integration API CLI (Protect 5.3+).

Auth: the per-user `custom.unifi-protect` credential holds the integration
key from Protect Settings > Control Plane > Integrations, sent as the
`X-API-KEY` header. The real key never touches this script: the runtime swaps
the surrogate on approved egress, only to the --host given at runtime.

--host is required on every run: the console base URL, e.g.
https://192.168.1.1 (the CLI appends /proxy/protect/integration/v1).
Consoles commonly use self-signed TLS certificates: verification stays ON by
default; pass --insecure only if the user accepts the risk (documented in the
skill).

Physical-world safety: reads (cameras, snapshot) are always safe. Camera
setting updates (PATCH) are LOW and proceed with a logged notice. PTZ moves,
flood-light toggles, chime sounding, and talkback are LOW-grade but their
exact write paths are UNTESTED open items (see below): they print a warning
and proceed with a logged notice.

OPEN ITEMS: the exact write paths for PTZ, talkback, lights, and chime could
not be pinned from public docs at build time. They ship as clearly-marked
UNTESTED path constants below; verify against the official Protect API
reference on first live use.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.unifi-protect"
API_PREFIX = "/proxy/protect/integration/v1"
CONFIRM_FILE = os.path.expanduser("~/.config/muse-connectors/unifi-protect/confirmed.json")

# UNTESTED write paths (open items). Do not trust until verified live.
PTZ_PATH_TEMPLATE = "/cameras/{id}/ptz"            # UNTESTED
TALKBACK_PATH_TEMPLATE = "/cameras/{id}/talkback"  # UNTESTED
LIGHTS_PATH_TEMPLATE = "/cameras/{id}/lights"      # UNTESTED
CHIME_PATH_TEMPLATE = "/cameras/{id}/chime"        # UNTESTED

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


def low_notice(effect: str) -> None:
    print(f"notice: LOW actuation proceeding: {effect}", file=sys.stderr)


def untested_warning(name: str) -> None:
    print(f"warning: the {name} write path is UNTESTED in this connector "
          "(open item); verify it against UniFi's Protect API reference on "
          "first live use.", file=sys.stderr)


# ---------------------------------------------------------------------------
# Auth + API plumbing
# ---------------------------------------------------------------------------

def base_url(args) -> str:
    host = args.host.rstrip("/")
    if not (host.startswith("http://") or host.startswith("https://")):
        sys.exit("error: --host must start with http:// or https://, e.g. "
                 "https://192.168.1.1")
    return host + API_PREFIX


def api_key() -> str:
    try:
        return str(dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]).strip()
    except DynamicCredentialError:
        print(
            "not connected: no custom.unifi-protect credential is stored.\n"
            "Collect it via the secure credential flow "
            "(credentials.request_api_access) as the Protect integration key "
            "(UniFi console > Protect Settings > Control Plane > Integrations "
            "> create an integration key), then retry. "
            "See this skill's SKILL.md Auth section.",
            file=sys.stderr,
        )
        sys.exit(1)


def ssl_context(args):
    if args.insecure:
        print("warning: TLS verification DISABLED (--insecure); the "
              "connection to the console is not authenticated.",
              file=sys.stderr)
        return ssl._create_unverified_context()
    return None  # default: verify


def call(args, method: str, path: str, payload: dict | None = None,
         raw: bool = False):
    base = base_url(args)
    url = base + path
    allowed = (urllib.parse.urlparse(base).hostname,)
    ensure_allowed_url(url, allowed_hosts=allowed)
    data = None
    headers = {"X-API-KEY": api_key()}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    ctx = ssl_context(args)
    try:
        if ctx is not None:
            resp = urllib.request.urlopen(req, timeout=30, context=ctx)
        else:
            resp = urllib.request.urlopen(req, timeout=30)
        with resp:
            body = resp.read()
            if raw:
                return body, resp.headers.get_content_type()
            try:
                return json.loads(body.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                return {"raw": body.decode("utf-8", errors="replace")[:500]}
    except urllib.error.HTTPError as exc:
        try:
            msg = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            msg = str(exc)
        sys.exit(f"error: unifi-protect returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure (incl. TLS errors)
        sys.exit(f"error: request failed: {exc}")


def parse_value(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_auth(args):
    cameras = call(args, "GET", "/cameras")
    count = len(cameras) if isinstance(cameras, list) else 0
    print(json.dumps({"ok": True, "host": args.host, "cameras": count},
                     indent=2))


def cmd_cameras(args):
    cameras = call(args, "GET", "/cameras")
    if isinstance(cameras, list):
        out = [{"id": c.get("id"), "name": c.get("name"),
                "modelKey": c.get("modelKey"), "state": c.get("state"),
                "isConnected": c.get("isConnected")}
               for c in cameras]
    else:
        out = cameras
    if args.limit and isinstance(out, list):
        out = out[:args.limit]
    print(json.dumps(out, indent=2))


def cmd_camera(args):
    result = call(args, "GET", f"/cameras/{args.id}")
    print(json.dumps(result, indent=2))


def cmd_snapshot(args):
    body, content_type = call(args, "GET", f"/cameras/{args.id}/snapshot",
                              raw=True)
    out = os.path.expanduser(args.out)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(body)
    print(json.dumps({"ok": True, "path": out, "bytes": len(body),
                      "content_type": content_type}, indent=2))


def cmd_patch(args):
    fields = {}
    for pair in args.field:
        if "=" not in pair:
            sys.exit("error: --field must be KEY=VALUE")
        k, _, v = pair.partition("=")
        fields[k] = parse_value(v)
    low_notice(f"update camera {args.id} settings: {fields} (changes "
               "microphone/recording behavior)")
    result = call(args, "PATCH", f"/cameras/{args.id}", fields)
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_ptz(args):
    untested_warning("PTZ")
    params = {}
    for name in ("pan", "tilt", "zoom"):
        value = getattr(args, name)
        if value is not None:
            params[name] = value
    if not params:
        sys.exit("error: pass at least one of --pan, --tilt, --zoom")
    low_notice(f"move PTZ motors on camera {args.id}: {params}")
    path = PTZ_PATH_TEMPLATE.format(id=urllib.parse.quote(args.id, safe=""))
    result = call(args, "POST", path, params)
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_lights(args):
    untested_warning("flood-light")
    on = args.on == "true"
    low_notice(f"turn the flood light {'on' if on else 'off'} on "
               f"camera {args.id}")
    path = LIGHTS_PATH_TEMPLATE.format(id=urllib.parse.quote(args.id, safe=""))
    result = call(args, "POST", path, {"on": on})
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_chime(args):
    untested_warning("chime")
    low_notice(f"sound the chime paired with camera {args.id}")
    path = CHIME_PATH_TEMPLATE.format(id=urllib.parse.quote(args.id, safe=""))
    result = call(args, "POST", path, {})
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_talkback(args):
    untested_warning("talkback")
    low_notice(f"send talkback audio through camera {args.id}'s speaker")
    path = TALKBACK_PATH_TEMPLATE.format(
        id=urllib.parse.quote(args.id, safe=""))
    result = call(args, "POST", path, {})
    print(json.dumps({"ok": True, "result": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="UniFi Protect Integration API CLI (muse-connectors). "
                    "--host is the console base URL. Reads (cameras, "
                    "snapshot) are always safe; PATCH camera updates are LOW "
                    "and proceed with a notice; PTZ, lights, chime, and "
                    "talkback ship with UNTESTED write paths.")
    parser.add_argument("--host", required=True,
                        help="console base URL, e.g. https://192.168.1.1")
    parser.add_argument("--insecure", action="store_true",
                        help="skip TLS verification (self-signed console "
                             "certs); verification is ON by default")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="status check: list cameras, verify key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("cameras", help="list cameras and their state")
    p.add_argument("--limit", type=int, default=0,
                   help="max cameras (0 = all)")
    p.set_defaults(func=cmd_cameras)

    p = sub.add_parser("camera", help="camera detail")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_camera)

    p = sub.add_parser("snapshot", help="save a still image from a camera")
    p.add_argument("--id", required=True)
    p.add_argument("--out", required=True, help="output file path, e.g. "
                                                "~/workspace/porch.jpg")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("patch", help="update camera settings (LOW: proceeds "
                                     "with a logged notice)")
    p.add_argument("--id", required=True)
    p.add_argument("--field", action="append", default=[], required=True,
                   help="KEY=VALUE setting (repeatable), e.g. "
                        "--field micEnabled=true")
    p.set_defaults(func=cmd_patch)

    p = sub.add_parser("ptz", help="UNTESTED path: move PTZ motors (LOW)")
    p.add_argument("--id", required=True)
    p.add_argument("--pan", type=float, default=None)
    p.add_argument("--tilt", type=float, default=None)
    p.add_argument("--zoom", type=float, default=None)
    p.set_defaults(func=cmd_ptz)

    p = sub.add_parser("lights", help="UNTESTED path: flood light on/off (LOW)")
    p.add_argument("--id", required=True)
    p.add_argument("--on", required=True, choices=("true", "false"),
                   help="true or false")
    p.set_defaults(func=cmd_lights)

    p = sub.add_parser("chime", help="UNTESTED path: sound the paired chime (LOW)")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_chime)

    p = sub.add_parser("talkback", help="UNTESTED path: talkback speaker (LOW)")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_talkback)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
