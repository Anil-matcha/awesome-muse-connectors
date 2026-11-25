#!/usr/bin/env python3
"""Minimal Home Assistant REST API CLI for the muse-connectors Home Assistant skill.

Auth: loads the per-user `custom.home-assistant` credential as a surrogate via
the bundled dynamic_credentials helper. The real token never touches this
script: the runtime swaps the surrogate on approved egress, only to the user's
own instance host (taken from --instance).

`call` acts on the physical home: always confirm with the user first.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.home-assistant"

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


def base_url(instance: str) -> tuple[str, tuple[str, ...]]:
    parsed = urllib.parse.urlparse(instance if "://" in instance else "https://" + instance)
    if not parsed.hostname:
        sys.exit("error: --instance must be a URL or hostname, e.g. https://home.example.com")
    base = f"{parsed.scheme or 'https'}://{parsed.hostname}"
    if parsed.port:
        base += f":{parsed.port}"
    return base, (parsed.hostname,)


def call(instance: str, path: str, payload: dict | None = None) -> list | dict:
    base, allowed_hosts = base_url(instance)
    url = base + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if payload is not None else "GET")
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=allowed_hosts)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        sys.exit(f"error: home-assistant returned HTTP {exc.code}: {detail}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    return result


def cmd_states(args):
    states = call(args.instance, "/api/states")
    if args.domain:
        states = [s for s in states if s.get("entity_id", "").startswith(args.domain + ".")]
    out = [{"entity_id": s.get("entity_id"), "state": s.get("state")} for s in states]
    print(json.dumps(out, indent=2))


def cmd_state(args):
    result = call(args.instance, f"/api/states/{args.entity}")
    print(json.dumps(
        {"entity_id": result.get("entity_id"), "state": result.get("state"),
         "attributes": result.get("attributes"), "last_changed": result.get("last_changed")},
        indent=2))


def cmd_call(args):
    payload = {}
    if args.entity:
        payload["entity_id"] = args.entity
    if args.data:
        try:
            payload.update(json.loads(args.data))
        except json.JSONDecodeError:
            sys.exit("error: --data must be valid JSON")
    result = call(args.instance, f"/api/services/{args.domain}/{args.service}", payload)
    print(json.dumps({"ok": True, "result": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Home Assistant REST API CLI (muse-connectors)")
    parser.add_argument("--instance", required=True,
                        help="instance URL, e.g. https://home.example.com")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("states", help="list entity states")
    p.add_argument("--domain", help="filter by domain, e.g. light")
    p.set_defaults(func=cmd_states)

    p = sub.add_parser("state", help="read one entity")
    p.add_argument("--entity", required=True, help="entity id, e.g. light.living_room")
    p.set_defaults(func=cmd_state)

    p = sub.add_parser("call", help="call a service (confirm with the user first)")
    p.add_argument("--domain", required=True, help="e.g. light")
    p.add_argument("--service", required=True, help="e.g. turn_on")
    p.add_argument("--entity", help="entity id, e.g. light.living_room")
    p.add_argument("--data", help='extra service data as JSON, e.g. {"temperature": 22}')
    p.set_defaults(func=cmd_call)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
