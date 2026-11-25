#!/usr/bin/env python3
"""Minimal Kit (ConvertKit) API CLI for the muse-connectors kit skill.

Auth: header `X-Kit-Api-Key: <key>` verbatim (NOT Bearer). Loads the
per-user `custom.kit` credential as a surrogate via the bundled
dynamic_credentials helper. The real API key never touches this script: the
runtime swaps the surrogate on approved egress, only to api.kit.com.

Broadcasts are created as drafts by default; `--send` sends to the list
(confirm with the user first). Sequence enrollments are confirmation-gated.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.kit"
ALLOWED_HOSTS = ("api.kit.com",)
API = "https://api.kit.com/v4"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        dynamic_credential_entry,
        ensure_allowed_url,
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
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        surrogate = dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    # Exact scheme: `X-Kit-Api-Key` header (NOT Bearer).
    req.add_header("X-Kit-Api-Key", surrogate)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("error", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: kit returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def list_items(result: dict) -> list:
    if not isinstance(result, dict):
        return []
    items = result.get("items", result.get("data", []))
    return items if isinstance(items, list) else []


def cmd_auth(_args):
    result = call("GET", "/subscribers", params={"per_page": 1})
    print(json.dumps({"ok": True, "subscribers": len(list_items(result))},
                     indent=2))


def cmd_subscribers(args):
    params = {"per_page": args.limit}
    result = call("GET", "/subscribers", params=params)
    subs = [
        {"id": s.get("id"), "email_address": s.get("email_address"),
         "first_name": s.get("first_name"), "state": s.get("state"),
         "created_at": s.get("created_at")}
        for s in list_items(result)
    ]
    print(json.dumps(subs, indent=2))


def cmd_broadcasts(args):
    params = {"per_page": args.limit}
    result = call("GET", "/broadcasts", params=params)
    broadcasts = [
        {"id": b.get("id"), "subject": b.get("subject"),
         "preview_text": b.get("preview_text"), "state": b.get("state"),
         "send_at": b.get("send_at"), "created_at": b.get("created_at")}
        for b in list_items(result)
    ]
    print(json.dumps(broadcasts, indent=2))


def cmd_broadcast_create(args):
    payload = {"subject": args.subject, "content": args.content}
    if args.preview_text:
        payload["preview_text"] = args.preview_text
    if args.json:
        try:
            payload.update(json.loads(args.json))
        except json.JSONDecodeError as exc:
            sys.exit(f"error: --json is not valid JSON: {exc}")
    if args.send:
        payload["send"] = True
    result = call("POST", "/broadcasts", payload=payload)
    broadcast = result.get("broadcast", result)
    if not isinstance(broadcast, dict):
        broadcast = {}
    print(json.dumps({"ok": True, "id": broadcast.get("id"),
                      "sent": bool(args.send)}, indent=2))


def cmd_sequences(args):
    params = {"per_page": args.limit}
    result = call("GET", "/sequences", params=params)
    sequences = [
        {"id": s.get("id"), "name": s.get("name"),
         "status": s.get("status"), "created_at": s.get("created_at")}
        for s in list_items(result)
    ]
    print(json.dumps(sequences, indent=2))


def cmd_tags(args):
    params = {"per_page": args.limit}
    result = call("GET", "/tags", params=params)
    tags = [
        {"id": t.get("id"), "name": t.get("name")}
        for t in list_items(result)
    ]
    print(json.dumps(tags, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Kit API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("subscribers", help="list subscribers")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_subscribers)

    p = sub.add_parser("broadcasts", help="list broadcasts")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_broadcasts)

    p = sub.add_parser("broadcast-create",
                       help="create a broadcast draft (confirm before --send)")
    p.add_argument("--subject", required=True)
    p.add_argument("--content", required=True, help="broadcast body (HTML)")
    p.add_argument("--preview-text", default=None)
    p.add_argument("--send", action="store_true",
                   help="send to the list NOW (confirmation-gated)")
    p.add_argument("--json", default=None,
                   help="extra broadcast fields as a JSON object")
    p.set_defaults(func=cmd_broadcast_create)

    p = sub.add_parser("sequences", help="list sequences")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_sequences)

    p = sub.add_parser("tags", help="list tags")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_tags)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
