#!/usr/bin/env python3
"""Minimal Coda API CLI for the muse-connectors Coda skill.

Auth: loads the per-user `custom.coda` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to coda.io.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.coda"
ALLOWED_HOSTS = ("coda.io",)
API = "https://coda.io/apis/v1"

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
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: coda returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    return result


def cmd_auth(_args):
    result = call("GET", "/whoami")
    print(json.dumps({
        "ok": True,
        "name": result.get("name"),
        "type": result.get("type"),
        "token_name": result.get("tokenName"),
        "workspace": (result.get("workspace") or {}).get("name"),
    }, indent=2))


def cmd_docs(args):
    result = call("GET", "/docs", params={"limit": args.limit})
    docs = [
        {"id": d["id"], "name": d.get("name"), "owner": d.get("ownerName"),
         "link": d.get("browserLink")}
        for d in result.get("items", [])
    ]
    print(json.dumps(docs, indent=2))


def cmd_tables(args):
    result = call("GET", f"/docs/{args.doc}/tables", params={"limit": args.limit})
    tables = [
        {"id": t["id"], "name": t.get("name"), "row_count": t.get("rowCount")}
        for t in result.get("items", [])
    ]
    print(json.dumps(tables, indent=2))


def cmd_rows(args):
    result = call("GET", f"/docs/{args.doc}/tables/{args.table}/rows",
                  params={"limit": args.limit, "useColumnNames": "true"})
    rows = [
        {"id": r["id"], "values": r.get("values")}
        for r in result.get("items", [])
    ]
    print(json.dumps(rows, indent=2))


def cmd_add_row(args):
    cells = json.loads(args.cells)
    payload = {"rows": [{"cells": cells}]}
    result = call("POST", f"/docs/{args.doc}/tables/{args.table}/rows", payload=payload)
    ids = [r.get("id") for r in result.get("addedRowIds", [])] if isinstance(
        result.get("addedRowIds"), list) else result.get("addedRowIds")
    print(json.dumps({"ok": True, "added": ids}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Coda API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection (whoami)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("docs", help="list docs")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_docs)

    p = sub.add_parser("tables", help="list tables in a doc")
    p.add_argument("--doc", required=True, help="doc ID")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_tables)

    p = sub.add_parser("rows", help="read rows from a table")
    p.add_argument("--doc", required=True)
    p.add_argument("--table", required=True, help="table ID or name")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_rows)

    p = sub.add_parser("add-row", help="add a row to a table (confirm first)")
    p.add_argument("--doc", required=True)
    p.add_argument("--table", required=True, help="table ID or name")
    p.add_argument("--cells", required=True,
                   help='JSON object of column name -> value, e.g. \'{"Task":"Ship","Done":false}\'')
    p.set_defaults(func=cmd_add_row)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
