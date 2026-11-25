#!/usr/bin/env python3
"""Minimal Webflow Data API v2 CLI for the muse-connectors Webflow skill.

Auth: per-site token loaded as a surrogate for `custom.webflow` via the
bundled dynamic_credentials helper (Bearer placement). The real token never
touches this script: the runtime swaps the surrogate on approved egress, only
to api.webflow.com.

Write bodies (--data) are passed through as raw JSON per the Webflow Data API
v2 docs; the CLI does not invent field shapes.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.webflow"
ALLOWED_HOSTS = ("api.webflow.com",)
API = "https://api.webflow.com/v2"

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


def credential_error(exc: Exception) -> None:
    sys.exit(
        "error: no stored credential for custom.webflow "
        f"({exc}). To connect, ask Muse to connect a Webflow site token via "
        "the secure credential flow, then retry."
    )


def api_error(exc: urllib.error.HTTPError) -> None:
    try:
        body = json.loads(exc.read().decode("utf-8", errors="replace"))
        msg = body.get("message") or body.get("msg") or str(exc)
    except Exception:
        msg = str(exc)
    sys.exit(f"error: webflow returned HTTP {exc.code}: {msg}")


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None})
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except (DynamicCredentialError, OSError) as exc:
        credential_error(exc)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        api_error(exc)
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def parse_data(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --data is not valid JSON: {exc}")


def cmd_auth(_args):
    result = call("GET", "/sites")
    sites = [{"id": s.get("id"), "displayName": s.get("displayName")} for s in result.get("sites", [])]
    print(json.dumps({"ok": True, "sites": sites}, indent=2))


def cmd_sites(_args):
    result = call("GET", "/sites")
    sites = [
        {"id": s.get("id"), "displayName": s.get("displayName"),
         "shortName": s.get("shortName"), "timeZone": s.get("timeZone")}
        for s in result.get("sites", [])
    ]
    print(json.dumps(sites, indent=2))


def cmd_site(args):
    result = call("GET", f"/sites/{args.id}")
    print(json.dumps(result, indent=2))


def cmd_collections(args):
    result = call("GET", f"/sites/{args.site_id}/collections")
    collections = [
        {"id": c.get("id"), "displayName": c.get("displayName"), "slug": c.get("slug")}
        for c in result.get("collections", [])
    ]
    print(json.dumps(collections, indent=2))


def cmd_items(args):
    result = call("GET", f"/collections/{args.collection_id}/items",
                  params={"limit": args.limit, "offset": args.offset})
    items = [
        {"id": i.get("id"), "fieldData": i.get("fieldData"),
         "isDraft": i.get("isDraft"), "isArchived": i.get("isArchived")}
        for i in result.get("items", [])
    ]
    print(json.dumps(items, indent=2))


def cmd_create_item(args):
    result = call("POST", f"/collections/{args.collection_id}/items",
                  payload=parse_data(args.data))
    items = [{"id": i.get("id"), "fieldData": i.get("fieldData")}
             for i in result.get("items", [])]
    print(json.dumps({"created": items}, indent=2))


def cmd_update_item(args):
    result = call("PATCH", f"/collections/{args.collection_id}/items/{args.item_id}",
                  payload=parse_data(args.data))
    print(json.dumps({"id": result.get("id"), "fieldData": result.get("fieldData")}, indent=2))


def cmd_delete_item(args):
    call("DELETE", f"/collections/{args.collection_id}/items/{args.item_id}")
    print(json.dumps({"deleted": True, "item_id": args.item_id}, indent=2))


def cmd_publish(args):
    payload = parse_data(args.data) if args.data else {}
    result = call("POST", f"/sites/{args.site_id}/publish", payload=payload)
    print(json.dumps({"published": True, "site_id": args.site_id,
                      "result": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Webflow Data API v2 CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection (lists accessible sites)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("sites", help="list sites")
    p.set_defaults(func=cmd_sites)

    p = sub.add_parser("site", help="get site details")
    p.add_argument("--id", required=True, help="site id")
    p.set_defaults(func=cmd_site)

    p = sub.add_parser("collections", help="list CMS collections on a site")
    p.add_argument("--site-id", required=True)
    p.set_defaults(func=cmd_collections)

    p = sub.add_parser("items", help="list CMS items in a collection")
    p.add_argument("--collection-id", required=True)
    p.add_argument("--limit", default=None)
    p.add_argument("--offset", default=None)
    p.set_defaults(func=cmd_items)

    p = sub.add_parser("create-item", help="create CMS item(s)")
    p.add_argument("--collection-id", required=True)
    p.add_argument("--data", required=True,
                   help="raw JSON body per the Webflow Data API v2 docs")
    p.set_defaults(func=cmd_create_item)

    p = sub.add_parser("update-item", help="update a CMS item")
    p.add_argument("--collection-id", required=True)
    p.add_argument("--item-id", required=True)
    p.add_argument("--data", required=True,
                   help="raw JSON body per the Webflow Data API v2 docs")
    p.set_defaults(func=cmd_update_item)

    p = sub.add_parser("delete-item", help="delete a CMS item")
    p.add_argument("--collection-id", required=True)
    p.add_argument("--item-id", required=True)
    p.set_defaults(func=cmd_delete_item)

    p = sub.add_parser("publish", help="publish a site")
    p.add_argument("--site-id", required=True)
    p.add_argument("--data", default=None,
                   help="optional raw JSON body (e.g. customDomains) per the docs")
    p.set_defaults(func=cmd_publish)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
