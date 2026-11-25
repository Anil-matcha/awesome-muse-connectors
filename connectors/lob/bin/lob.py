#!/usr/bin/env python3
"""Minimal Lob Print & Mail API CLI for the muse-connectors lob skill.

Auth: loads the per-user `custom.lob` API key as a surrogate via the
bundled dynamic_credentials helper. Lob authenticates with HTTP Basic (API
key as username, blank password); the placement is resolved by the helper
from the credential config. The real key never touches this script: the
runtime swaps the surrogate on approved egress, only to api.lob.com.

Safety: live sends (postcards/letters) are a HIGH actuation (physical piece
printed and mailed, postage charged, irreversible once production starts).
They require --live AND an exact --confirm string echoed by the CLI. Test
keys simulate the full lifecycle free.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.lob"
ALLOWED_HOSTS = ("api.lob.com",)
API = "https://api.lob.com/v1"
CONNECT_GUIDANCE = (
    "not connected: collect a Lob API key (Lob dashboard -> API keys) via "
    "the secure credential flow (credentials.request_api_access) as "
    "`custom.lob`, then retry. Use a test_ key for dry runs."
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            err = body.get("error") or {}
            msg = err.get("message", str(exc)) if isinstance(err, dict) else str(exc)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: lob returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def load_file(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        sys.exit(f"error: could not read JSON file {path}: {exc}")


def describe_recipient(payload: dict) -> str:
    to = payload.get("to") or {}
    name = to.get("name") or "?"
    addr = to.get("address_line1") or to.get("address_line2") or "?"
    return f"{name} at {addr}"


def cmd_auth(_args):
    result = call("GET", "/postcards?limit=1")
    print(json.dumps({"ok": True, "postcards_total": result.get("count")},
                     indent=2))


def cmd_verify_address(args):
    payload = load_file(args.file)
    result = call("POST", "/us_verifications", payload)
    print(json.dumps(result, indent=2))


def cmd_send(resource: str, args):
    payload = load_file(args.file)
    recipient = describe_recipient(payload)
    expected = f"mail {resource} to {recipient}"
    if args.confirm != expected:
        effect = ("a LIVE send prints a physical piece, mails it, and charges "
                  "printing plus postage; it cannot be recalled once "
                  "production starts")
        sys.exit(
            f"refusing: {effect}\n"
            f"Re-run with the exact confirmation string:\n"
            f'  --confirm "{expected}"\n'
            f'Add --live as well when the stored key is a live_ key '
            f'(your explicit acknowledgment that real mail goes out).'
        )
    result = call("POST", f"/{resource}s", payload)
    if args.live:
        note = ("LIVE send: piece will be printed and mailed; printing plus "
                "postage charged; irreversible once production starts.")
    else:
        note = ("assumed test key: lifecycle simulated, nothing printed or "
                "charged. WARNING: if the stored key is actually a live_ "
                "key, this mailed for real; keep test_ keys stored for "
                "routine use.")
    print(json.dumps({"ok": True, "live": args.live, "id": result.get("id"),
                      "expected_delivery_date":
                      result.get("expected_delivery_date"),
                      "note": note}, indent=2))


def cmd_postcards(args):
    result = call("GET", f"/postcards?limit={args.limit}")
    items = [{"id": p.get("id"), "to": (p.get("to") or {}).get("name"),
              "send_date": p.get("send_date"),
              "expected_delivery_date": p.get("expected_delivery_date")}
             for p in result.get("data", [])]
    print(json.dumps(items, indent=2))


def cmd_get_letter(args):
    result = call("GET", f"/letters/{args.id}")
    print(json.dumps({"id": result.get("id"),
                      "to": (result.get("to") or {}).get("name"),
                      "send_date": result.get("send_date"),
                      "expected_delivery_date":
                      result.get("expected_delivery_date")}, indent=2))


def cmd_cancel(resource: str, args):
    result = call("DELETE", f"/{resource}s/{args.id}")
    deleted = result.get("deleted", True)
    print(json.dumps({"ok": True, "id": args.id, "deleted": deleted,
                      "note": "cancellation only works pre-production; once "
                              "production starts the piece cannot be "
                              "recalled"}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Lob Print & Mail API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("verify-address",
                       help="verify/correct a US address (no mail sent)")
    p.add_argument("--file", required=True,
                   help="JSON file with the address payload")
    p.set_defaults(func=cmd_verify_address)

    p = sub.add_parser("send-postcard", help="create and send a postcard")
    p.add_argument("--file", required=True,
                   help="JSON file with the postcard payload (to, from, "
                        "front, back, size)")
    p.add_argument("--live", action="store_true",
                   help="acknowledge this runs against a live key "
                        "(prints and mails for real)")
    p.add_argument("--confirm", default=None,
                   help="exact confirmation string echoed by the CLI")
    p.set_defaults(func=lambda a: cmd_send("postcard", a))

    p = sub.add_parser("send-letter", help="create and send a letter")
    p.add_argument("--file", required=True,
                   help="JSON file with the letter payload (to, from, file, "
                        "color)")
    p.add_argument("--live", action="store_true",
                   help="acknowledge this runs against a live key "
                        "(prints and mails for real)")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=lambda a: cmd_send("letter", a))

    p = sub.add_parser("postcards", help="list postcards")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_postcards)

    p = sub.add_parser("get-letter", help="retrieve a letter")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_get_letter)

    p = sub.add_parser("cancel-postcard", help="cancel a postcard (pre-production only)")
    p.add_argument("--id", required=True)
    p.set_defaults(func=lambda a: cmd_cancel("postcard", a))

    p = sub.add_parser("cancel-letter", help="cancel a letter (pre-production only)")
    p.add_argument("--id", required=True)
    p.set_defaults(func=lambda a: cmd_cancel("letter", a))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
