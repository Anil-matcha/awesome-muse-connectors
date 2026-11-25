#!/usr/bin/env python3
"""Minimal Patreon API CLI for the muse-connectors patreon skill.

Auth: OAuth 2.0 (`Authorization: Bearer <token>`). For personal use, the
Creator's Access Token is issued from the client portal (self-serve, no app
review for your own data). Loads the per-user `custom.patreon` credential
as a surrogate via the bundled dynamic_credentials helper. The real token
never touches this script: the runtime swaps the surrogate on approved
egress, only to www.patreon.com.

Effectively READ-ONLY: Patreon exposes no creator write endpoints, so this
CLI has no writes and zero write risk.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.patreon"
ALLOWED_HOSTS = ("www.patreon.com",)
API = "https://www.patreon.com/api/oauth2/v2"

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


def call(path: str, params: dict | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME,
                                 allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error_description", body.get("error", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: patreon returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def one(resource: dict) -> dict:
    """Defensively unwrap a JSON:API resource (id + nested attributes)."""
    if not isinstance(resource, dict):
        return {}
    attrs = resource.get("attributes", {})
    row = {"id": resource.get("id"), "type": resource.get("type")}
    if isinstance(attrs, dict):
        row.update(attrs)
    return row


def many(result: dict) -> list:
    if not isinstance(result, dict):
        return []
    data = result.get("data", [])
    items = data if isinstance(data, list) else [data]
    return [one(item) for item in items]


def cmd_auth(_args):
    result = call("/identity", params={"include": "memberships,campaign",
                                       "fields[user]": "full_name,email",
                                       "fields[campaign]": "patron_count"})
    rows = many(result)
    user = rows[0] if rows else {}
    print(json.dumps({"ok": True, "id": user.get("id"),
                      "full_name": user.get("full_name"),
                      "email": user.get("email")}, indent=2))


def cmd_identity(args):
    params = {}
    if args.include:
        params["include"] = args.include
    result = call("/identity", params=params)
    print(json.dumps(many(result), indent=2))


def cmd_campaign(args):
    result = call(f"/campaigns/{args.campaign_id}")
    print(json.dumps(one(result.get("data", {})), indent=2))


def cmd_members(args):
    params = {"page[size]": args.limit}
    if args.include:
        params["include"] = args.include
    result = call(f"/campaigns/{args.campaign_id}/members", params=params)
    print(json.dumps(many(result), indent=2))


def cmd_tiers(args):
    params = {"page[size]": args.limit}
    result = call(f"/campaigns/{args.campaign_id}/tiers", params=params)
    print(json.dumps(many(result), indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Patreon API CLI (muse-connectors; read-only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the access token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("identity", help="show the current user")
    p.add_argument("--include", default=None,
                   help="comma-separated includes, e.g. memberships,campaign")
    p.set_defaults(func=cmd_identity)

    p = sub.add_parser("campaign", help="show a campaign")
    p.add_argument("--campaign-id", required=True)
    p.set_defaults(func=cmd_campaign)

    p = sub.add_parser("members", help="list campaign members")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--include", default=None)
    p.set_defaults(func=cmd_members)

    p = sub.add_parser("tiers", help="list campaign tiers")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_tiers)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
