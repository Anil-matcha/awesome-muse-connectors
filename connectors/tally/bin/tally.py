#!/usr/bin/env python3
"""Minimal Tally API CLI for the muse-connectors tally skill.

Auth: loads the per-user `custom.tally` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.tally.so.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.tally"
ALLOWED_HOSTS = ("api.tally.so",)
API = "https://api.tally.so"

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


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
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
        sys.exit(f"error: tally returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def items(result) -> list:
    # Tally wraps lists as {"data": [...], "meta": {...}}.
    if isinstance(result, dict) and isinstance(result.get("data"), list):
        return result["data"]
    if isinstance(result, list):
        return result
    return []


def cmd_auth(_args):
    result = call("GET", "/forms", params={"limit": 1})
    print(json.dumps({"ok": True, "forms": len(items(result))}, indent=2))


def cmd_forms(args):
    result = call("GET", "/forms", params={"limit": args.limit})
    forms = [
        {"id": f.get("id"), "name": f.get("name"),
         "status": f.get("status")}
        for f in items(result)
    ]
    print(json.dumps(forms, indent=2))


def cmd_form(args):
    result = call("GET", f"/forms/{args.id}")
    print(json.dumps(result, indent=2))


def cmd_create(args):
    result = call("POST", "/forms", payload={"name": args.name})
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "name": result.get("name")}, indent=2))


def cmd_update(args):
    # PATCH replaces the whole blocks array, so the caller passes the FULL
    # new blocks array in --blocks-file (fetch it first with `form --id`).
    try:
        with open(args.blocks_file, "r", encoding="utf-8") as fh:
            blocks = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"error: could not read blocks file: {exc}")
    if not isinstance(blocks, list):
        sys.exit("error: blocks file must contain a JSON array of blocks")
    payload = {"blocks": blocks}
    if args.name:
        payload["name"] = args.name
    result = call("PATCH", f"/forms/{args.id}", payload=payload)
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "name": result.get("name"),
                      "blocks": len(result.get("blocks", []))}, indent=2))


def cmd_submissions(args):
    result = call("GET", f"/forms/{args.id}/submissions",
                  params={"limit": args.limit})
    print(json.dumps(items(result), indent=2))


def main():
    parser = argparse.ArgumentParser(description="Tally API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("forms", help="list forms")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_forms)

    p = sub.add_parser("form", help="fetch one form with its blocks")
    p.add_argument("--id", required=True, help="form ID")
    p.set_defaults(func=cmd_form)

    p = sub.add_parser("create", help="create a form (confirm first)")
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("update", help="replace a form's blocks (confirm first)")
    p.add_argument("--id", required=True, help="form ID")
    p.add_argument("--blocks-file", required=True,
                   help="JSON file with the FULL new blocks array "
                        "(fetch current blocks with `form --id` first)")
    p.add_argument("--name", default=None, help="rename the form")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("submissions", help="read form submissions")
    p.add_argument("--id", required=True, help="form ID")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_submissions)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
