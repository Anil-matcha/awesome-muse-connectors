#!/usr/bin/env python3
"""Minimal Dub API CLI for the muse-connectors dub skill.

Auth: loads the per-user `custom.dub` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.dub.co.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.dub"
ALLOWED_HOSTS = ("api.dub.co",)
API = "https://api.dub.co"  # Dub paths are UNVERSIONED (no /v2)

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
         payload: dict | None = None):
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
            msg = body.get("error", {}).get("message", body.get("error", str(exc)))
            if isinstance(msg, dict):
                msg = str(exc)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: dub returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = call("GET", "/links", params={"limit": 1})
    print(json.dumps({"ok": True, "links": len(result)}, indent=2))


def cmd_links(args):
    result = call("GET", "/links", params={"limit": args.limit})
    links = [
        {"id": l["id"], "domain": l.get("domain"), "key": l.get("key"),
         "url": l.get("url"), "shortLink": l.get("shortLink"),
         "clicks": l.get("clicks")}
        for l in result
    ]
    print(json.dumps(links, indent=2))


def cmd_create(args):
    payload = {"url": args.url}
    if args.key:
        payload["key"] = args.key
    if args.domain:
        payload["domain"] = args.domain
    result = call("POST", "/links", payload=payload)
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "shortLink": result.get("shortLink"),
                      "url": result.get("url")}, indent=2))


def cmd_update(args):
    payload = {}
    if args.url:
        payload["url"] = args.url
    if args.key:
        payload["key"] = args.key
    if args.domain:
        payload["domain"] = args.domain
    if not payload:
        sys.exit("error: nothing to update; pass at least one of --url, --key, --domain")
    result = call("PATCH", f"/links/{args.id}", payload=payload)
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "shortLink": result.get("shortLink")}, indent=2))


def cmd_delete(args):
    call("DELETE", f"/links/{args.id}")
    print(json.dumps({"ok": True, "id": args.id}, indent=2))


def cmd_analytics(args):
    params = {"linkId": args.link_id}
    if args.interval:
        params["interval"] = args.interval
    result = call("GET", "/analytics", params=params)
    print(json.dumps(result, indent=2))


def cmd_track_lead(args):
    payload = {"clickId": args.click_id}
    if args.event_name:
        payload["eventName"] = args.event_name
    if args.customer_id:
        payload["customerId"] = args.customer_id
    result = call("POST", "/track/lead", payload=payload)
    print(json.dumps(result, indent=2))


def cmd_track_sale(args):
    payload = {"clickId": args.click_id}
    if args.event_name:
        payload["eventName"] = args.event_name
    if args.customer_id:
        payload["customerId"] = args.customer_id
    sale = {}
    if args.amount is not None:
        sale["amount"] = args.amount
    if args.currency:
        sale["currency"] = args.currency
    if sale:
        payload["sale"] = sale
    result = call("POST", "/track/sale", payload=payload)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Dub API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("links", help="list links")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_links)

    p = sub.add_parser("create", help="create a short link (confirm first)")
    p.add_argument("--url", required=True, help="destination URL")
    p.add_argument("--key", default=None, help="custom link key/slug")
    p.add_argument("--domain", default=None, help="short domain")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("update", help="update a link (confirm first)")
    p.add_argument("--id", required=True, help="link ID")
    p.add_argument("--url", default=None, help="new destination URL")
    p.add_argument("--key", default=None, help="new link key/slug")
    p.add_argument("--domain", default=None, help="new short domain")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("delete", help="delete a link (confirm first)")
    p.add_argument("--id", required=True, help="link ID")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("analytics", help="click analytics for a link")
    p.add_argument("--link-id", required=True, help="link ID")
    p.add_argument("--interval", default=None,
                   help="e.g. 24h, 7d, 30d, mtd, all")
    p.set_defaults(func=cmd_analytics)

    p = sub.add_parser("track-lead", help="record a lead conversion (confirm first)")
    p.add_argument("--click-id", required=True)
    p.add_argument("--event-name", default=None)
    p.add_argument("--customer-id", default=None)
    p.set_defaults(func=cmd_track_lead)

    p = sub.add_parser("track-sale", help="record a sale conversion (confirm first)")
    p.add_argument("--click-id", required=True)
    p.add_argument("--amount", type=int, default=None,
                   help="sale amount in cents")
    p.add_argument("--currency", default=None, help="e.g. USD")
    p.add_argument("--event-name", default=None)
    p.add_argument("--customer-id", default=None)
    p.set_defaults(func=cmd_track_sale)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
