#!/usr/bin/env python3
"""Minimal Apollo.io API CLI for the muse-connectors Apollo skill.

Auth: loads the per-user `custom.apollo` credential as a surrogate via the
bundled dynamic_credentials helper. Apollo authenticates with the `x-api-key`
header whose value is the raw API key; the placement is resolved by the helper
from the credential config. The real key never touches this script: the
runtime swaps the surrogate on approved egress, only to api.apollo.io.

Note: Apollo API access requires a Professional plan or higher, and enrichment
calls consume Apollo credits.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.apollo"
ALLOWED_HOSTS = ("api.apollo.io",)
API = "https://api.apollo.io/api/v1"

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
    headers = {"Content-Type": "application/json", "Cache-Control": "no-cache"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
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
            msg = body.get("error", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: apollo returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def shape_person(p: dict) -> dict:
    org = p.get("organization") or {}
    return {
        "id": p.get("id"),
        "name": " ".join(x for x in [p.get("first_name"), p.get("last_name")]
                         if x),
        "title": p.get("title"),
        "email": p.get("email"),
        "linkedin_url": p.get("linkedin_url"),
        "organization": org.get("name"),
        "org_domain": org.get("primary_domain"),
    }


def cmd_auth(_args):
    result = call("GET", "/auth/health")
    print(json.dumps({"ok": result.get("is_healthy", True),
                      "health": result}, indent=2))


def cmd_search(args):
    payload = {"page": args.page, "per_page": args.limit}
    if args.titles:
        payload["person_titles"] = [t.strip() for t in args.titles.split(",")]
    if args.locations:
        payload["person_locations"] = [l.strip() for l in args.locations.split(",")]
    if args.domains:
        payload["q_organization_domains_list"] = [
            d.strip() for d in args.domains.split(",")]
    result = call("POST", "/mixed_people/api_search", payload=payload)
    people = [shape_person(p) for p in result.get("people", [])]
    print(json.dumps({"total_entries": result.get("total_entries"),
                      "people": people}, indent=2))


def cmd_enrich(args):
    payload = {}
    if args.email:
        payload["email"] = args.email
    if args.first_name:
        payload["first_name"] = args.first_name
    if args.last_name:
        payload["last_name"] = args.last_name
    if args.domain:
        payload["domain"] = args.domain
    if args.linkedin_url:
        payload["linkedin_url"] = args.linkedin_url
    result = call("POST", "/people/match", payload=payload)
    person = result.get("person") or {}
    print(json.dumps(shape_person(person), indent=2))


def cmd_org_enrich(args):
    result = call("GET", f"/organizations/enrich?domain={args.domain}")
    org = result.get("organization") or {}
    print(json.dumps({
        "id": org.get("id"), "name": org.get("name"),
        "domain": org.get("primary_domain"), "industry": org.get("industry"),
        "employees": org.get("estimated_num_employees"),
        "linkedin_url": org.get("linkedin_url"),
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Apollo.io API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("search", help="search people (free, no credits)")
    p.add_argument("--titles", default=None,
                   help="job titles, comma-separated")
    p.add_argument("--locations", default=None,
                   help="locations, comma-separated")
    p.add_argument("--domains", default=None,
                   help="company domains, comma-separated")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--page", type=int, default=1)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("enrich", help="enrich one person (consumes credits)")
    p.add_argument("--email", default=None)
    p.add_argument("--first-name", default=None)
    p.add_argument("--last-name", default=None)
    p.add_argument("--domain", default=None)
    p.add_argument("--linkedin-url", default=None)
    p.set_defaults(func=cmd_enrich)

    p = sub.add_parser("org-enrich", help="enrich one company by domain")
    p.add_argument("--domain", required=True)
    p.set_defaults(func=cmd_org_enrich)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
