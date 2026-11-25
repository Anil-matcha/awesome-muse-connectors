#!/usr/bin/env python3
"""Minimal Clerk Backend API CLI for the muse-connectors clerk skill.

Auth: loads the per-user `custom.clerk` credential as a surrogate via the
bundled dynamic_credentials helper. The real secret key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.clerk.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.clerk"
ALLOWED_HOSTS = ("api.clerk.com",)
API = "https://api.clerk.com"

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
            errors = body.get("errors", [])
            msg = errors[0].get("message") if errors else body.get("error", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: Clerk returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def summarize_user(u: dict) -> dict:
    emails = [e.get("email_address") for e in (u.get("email_addresses") or [])]
    return {"id": u.get("id"), "first_name": u.get("first_name"),
            "last_name": u.get("last_name"), "emails": emails,
            "created_at": u.get("created_at")}


def cmd_auth(_args):
    result = call("GET", "/v1/users", params={"limit": 1})
    users = result.get("data", [])
    print(json.dumps({"ok": True, "users": len(users),
                      "first": summarize_user(users[0])
                      if users else None}, indent=2))


def cmd_users(args):
    result = call("GET", "/v1/users", params={"limit": args.limit})
    print(json.dumps([summarize_user(u)
                      for u in result.get("data", [])], indent=2))


def cmd_user(args):
    result = call("GET", f"/v1/users/{args.id}")
    print(json.dumps(summarize_user(result), indent=2))


def cmd_create(args):
    payload: dict = {"email_address": [args.email]}
    if args.first_name is not None:
        payload["first_name"] = args.first_name
    if args.last_name is not None:
        payload["last_name"] = args.last_name
    result = call("POST", "/v1/users", payload=payload)
    print(json.dumps({"ok": True, "user": summarize_user(result)}, indent=2))


def cmd_update(args):
    payload: dict = {}
    if args.first_name is not None:
        payload["first_name"] = args.first_name
    if args.last_name is not None:
        payload["last_name"] = args.last_name
    if not payload:
        sys.exit("error: nothing to update (pass --first-name and/or --last-name)")
    result = call("PATCH", f"/v1/users/{args.id}", payload=payload)
    print(json.dumps({"ok": True, "user": summarize_user(result)}, indent=2))


def cmd_delete(args):
    result = call("DELETE", f"/v1/users/{args.id}")
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "deleted": result.get("object") == "user"}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Clerk Backend API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the secret key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("users", help="list users")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_users)

    p = sub.add_parser("user", help="look up one user")
    p.add_argument("--id", required=True, help="user ID")
    p.set_defaults(func=cmd_user)

    p = sub.add_parser("create", help="create a user (confirm first)")
    p.add_argument("--email", required=True)
    p.add_argument("--first-name", default=None)
    p.add_argument("--last-name", default=None)
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("update", help="update a user (confirm first)")
    p.add_argument("--id", required=True, help="user ID")
    p.add_argument("--first-name", default=None)
    p.add_argument("--last-name", default=None)
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("delete", help="delete a user (confirm first; irreversible)")
    p.add_argument("--id", required=True, help="user ID")
    p.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
