#!/usr/bin/env python3
"""Minimal HubSpot CRM API CLI for the muse-connectors HubSpot skill.

Auth: loads the per-user `custom.hubspot` credential (a private app token) as
a surrogate via the bundled dynamic_credentials helper. The real token never
touches this script: the runtime swaps the surrogate on approved egress, only
to api.hubapi.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.hubspot"
ALLOWED_HOSTS = ("api.hubapi.com",)
API = "https://api.hubapi.com"


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


def call(path: str, params: dict | None = None, payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except Exception as exc:  # network-level failure (HTTP errors surface here)
        sys.exit(f"error: request failed: {exc}")


def slim_contact(c: dict) -> dict:
    props = c.get("properties") or {}
    return {
        "id": c.get("id"),
        "email": props.get("email"),
        "firstname": props.get("firstname"),
        "lastname": props.get("lastname"),
        "company": props.get("company"),
    }


def cmd_contacts(args):
    result = call(
        "/crm/v3/objects/contacts",
        params={"limit": args.limit, "properties": "firstname,lastname,email,company"},
    )
    print(json.dumps([slim_contact(c) for c in result.get("results", [])], indent=2))


def cmd_search_contacts(args):
    result = call("/crm/v3/objects/contacts/search", payload={"query": args.query})
    print(json.dumps([slim_contact(c) for c in result.get("results", [])], indent=2))


def cmd_create_contact(args):
    props = {"email": args.email}
    if args.firstname:
        props["firstname"] = args.firstname
    if args.lastname:
        props["lastname"] = args.lastname
    result = call("/crm/v3/objects/contacts", payload={"properties": props})
    print(json.dumps(slim_contact(result), indent=2))


def cmd_deals(args):
    result = call(
        "/crm/v3/objects/deals",
        params={"limit": args.limit, "properties": "dealname,amount,dealstage"},
    )
    out = []
    for d in result.get("results", []):
        props = d.get("properties") or {}
        out.append({
            "id": d.get("id"),
            "dealname": props.get("dealname"),
            "amount": props.get("amount"),
            "dealstage": props.get("dealstage"),
        })
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="HubSpot CRM API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("contacts", help="list contacts")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_contacts)

    p = sub.add_parser("search-contacts", help="search contacts")
    p.add_argument("--query", required=True)
    p.set_defaults(func=cmd_search_contacts)

    p = sub.add_parser("create-contact", help="create a contact")
    p.add_argument("--email", required=True)
    p.add_argument("--firstname")
    p.add_argument("--lastname")
    p.set_defaults(func=cmd_create_contact)

    p = sub.add_parser("deals", help="list deals")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_deals)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
