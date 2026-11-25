#!/usr/bin/env python3
"""Minimal Airtable Web API CLI for the muse-connectors Airtable skill.

Auth: loads the per-user `custom.airtable` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api.airtable.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.airtable"
ALLOWED_HOSTS = ("api.airtable.com",)
API = "https://api.airtable.com/v0"

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


def call(method: str, path: str, payload: dict | None = None, params: dict | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            detail = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            detail = str(exc)
        sys.exit(f"error: airtable returned HTTP {exc.code}: {detail}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    return result


def cmd_bases(_args):
    result = call("GET", "/meta/bases")
    bases = [{"id": b.get("id"), "name": b.get("name")}
             for b in result.get("bases", [])]
    print(json.dumps(bases, indent=2))


def cmd_records(args):
    result = call("GET", f"/{args.base}/{urllib.parse.quote(args.table)}",
                  params={"maxRecords": args.limit})
    out = []
    for r in result.get("records", []):
        row = {"id": r.get("id")}
        row.update(r.get("fields", {}) or {})
        out.append(row)
    print(json.dumps(out, indent=2))


def cmd_create(args):
    try:
        fields = json.loads(args.fields)
    except json.JSONDecodeError:
        sys.exit("error: --fields must be valid JSON, e.g. '{\"Name\": \"Buy milk\"}'")
    if not isinstance(fields, dict):
        sys.exit("error: --fields must be a JSON object of field names to values")
    result = call("POST", f"/{args.base}/{urllib.parse.quote(args.table)}",
                  payload={"fields": fields})
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "fields": result.get("fields")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Airtable Web API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("bases", help="list bases")
    p.set_defaults(func=cmd_bases)

    p = sub.add_parser("records", help="read table records")
    p.add_argument("--base", required=True, help="base id, e.g. appABC123")
    p.add_argument("--table", required=True, help="table name as shown in the base")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_records)

    p = sub.add_parser("create", help="add a record")
    p.add_argument("--base", required=True, help="base id, e.g. appABC123")
    p.add_argument("--table", required=True, help="table name as shown in the base")
    p.add_argument("--fields", required=True,
                   help="record fields as JSON, e.g. '{\"Name\": \"Buy milk\"}'")
    p.set_defaults(func=cmd_create)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
