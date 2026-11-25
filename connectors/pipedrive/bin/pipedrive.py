#!/usr/bin/env python3
"""Minimal Pipedrive API CLI for the muse-connectors Pipedrive skill.

Auth: loads the per-user `custom.pipedrive` credential as a surrogate via the
bundled dynamic_credentials helper. Pipedrive's personal API token travels as
the `api_token` query parameter on the user's company subdomain
(`{company}.pipedrive.com`), so the CLI uses the helper's query-param
placement: the runtime swaps the surrogate into the URL on approved egress,
only to that company's host. Pass --company once per invocation (the part
before .pipedrive.com in your Pipedrive URL).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.pipedrive"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        read_json_response,
        url_with_surrogate_query_param,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def check_company(company: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", company or ""):
        sys.exit("error: --company must be your Pipedrive subdomain "
                 "(e.g. acme for acme.pipedrive.com)")
    return company.lower()


def call(company: str, method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    company = check_company(company)
    host = f"{company}.pipedrive.com"
    url = f"https://{host}/api/v1" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        url = url_with_surrogate_query_param(
            url, CREDENTIAL_NAME, allowed_hosts=(host,))
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: pipedrive returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if not result.get("success"):
        sys.exit(f"error: pipedrive: {result.get('error')}")
    return result.get("data")


def cmd_auth(args):
    me = call(args.company, "GET", "/users/me")
    print(json.dumps({"ok": True, "id": me.get("id"), "name": me.get("name"),
                      "email": me.get("email"),
                      "company": me.get("company_name")}, indent=2))


def cmd_deals(args):
    deals = call(args.company, "GET", "/deals",
                 params={"limit": args.limit, "status": args.status})
    out = [
        {"id": d["id"], "title": d.get("title"), "value": d.get("value"),
         "currency": d.get("currency"), "stage": (d.get("stage_id")),
         "person": (d.get("person_id") or {}).get("name"),
         "org": (d.get("org_id") or {}).get("name")}
        for d in (deals or [])
    ]
    print(json.dumps(out, indent=2))


def cmd_persons(args):
    persons = call(args.company, "GET", "/persons",
                   params={"limit": args.limit})
    out = [
        {"id": p["id"], "name": p.get("name"),
         "email": [(e.get("value")) for e in p.get("email", [])],
         "org": (p.get("org_id") or {}).get("name")}
        for p in (persons or [])
    ]
    print(json.dumps(out, indent=2))


def cmd_create_deal(args):
    payload = {"title": args.title}
    if args.value:
        payload["value"] = args.value
    if args.person_id:
        payload["person_id"] = args.person_id
    if args.org_id:
        payload["org_id"] = args.org_id
    deal = call(args.company, "POST", "/deals", payload=payload)
    print(json.dumps({"ok": True, "id": deal.get("id"),
                      "title": deal.get("title")}, indent=2))


def add_company_arg(p):
    p.add_argument("--company", required=True,
                   help="your Pipedrive subdomain (acme for acme.pipedrive.com)")


def main():
    parser = argparse.ArgumentParser(description="Pipedrive API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API token")
    add_company_arg(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("deals", help="list deals")
    add_company_arg(p)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--status", default="open",
                   help="open, won, lost, deleted, all_not_deleted")
    p.set_defaults(func=cmd_deals)

    p = sub.add_parser("persons", help="list contacts")
    add_company_arg(p)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_persons)

    p = sub.add_parser("create-deal", help="create a deal (confirm first)")
    add_company_arg(p)
    p.add_argument("--title", required=True)
    p.add_argument("--value", type=float, default=None)
    p.add_argument("--person-id", type=int, default=None)
    p.add_argument("--org-id", type=int, default=None)
    p.set_defaults(func=cmd_create_deal)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
