#!/usr/bin/env python3
"""Minimal beehiiv API CLI for the muse-connectors beehiiv skill.

Auth: loads the per-user `custom.beehiiv` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.beehiiv.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.beehiiv"
ALLOWED_HOSTS = ("api.beehiiv.com",)
API = "https://api.beehiiv.com/v2"

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
            msg = body.get("message", body.get("error", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: beehiiv returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = call("GET", "/publications", params={"limit": 1})
    pubs = result.get("data", [])
    print(json.dumps({"ok": True, "publications": len(pubs),
                      "first": pubs[0].get("name") if pubs else None}, indent=2))


def cmd_publications(args):
    result = call("GET", "/publications", params={"limit": args.limit})
    pubs = [
        {"id": p["id"], "name": p.get("name"), "subdomain": p.get("subdomain")}
        for p in result.get("data", [])
    ]
    print(json.dumps(pubs, indent=2))


def cmd_subscriptions(args):
    result = call("GET", f"/publications/{args.pub}/subscriptions",
                  params={"limit": args.limit})
    subs = [
        {"id": s["id"], "email": s.get("email"),
         "status": s.get("status"), "tier": s.get("tier")}
        for s in result.get("data", [])
    ]
    print(json.dumps(subs, indent=2))


def cmd_posts(args):
    result = call("GET", f"/publications/{args.pub}/posts",
                  params={"limit": args.limit, "order": "desc",
                          "order_by": "publish_date"})
    posts = [
        {"id": p["id"], "title": p.get("title"), "status": p.get("status"),
         "publish_date": p.get("publish_date"),
         "stats": p.get("stats")}
        for p in result.get("data", [])
    ]
    print(json.dumps(posts, indent=2))


def cmd_subscribe(args):
    payload = {"email": args.email}
    if args.tier:
        payload["tier"] = args.tier
    result = call("POST", f"/publications/{args.pub}/subscriptions",
                  payload=payload)
    sub = result.get("data", {})
    print(json.dumps({"ok": True, "id": sub.get("id"),
                      "email": sub.get("email")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="beehiiv API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("publications", help="list publications")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_publications)

    p = sub.add_parser("subscriptions", help="list subscribers")
    p.add_argument("--pub", required=True, help="publication ID (pub_...)")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_subscriptions)

    p = sub.add_parser("posts", help="list posts")
    p.add_argument("--pub", required=True, help="publication ID (pub_...)")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_posts)

    p = sub.add_parser("subscribe", help="add a subscriber (confirm first)")
    p.add_argument("--pub", required=True, help="publication ID (pub_...)")
    p.add_argument("--email", required=True)
    p.add_argument("--tier", default=None, help="free or premium")
    p.set_defaults(func=cmd_subscribe)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
