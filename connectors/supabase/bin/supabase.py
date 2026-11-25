#!/usr/bin/env python3
"""Supabase PostgREST CLI for the muse-connectors supabase skill.

Auth: loads the per-user `custom.supabase` credential as a surrogate via the
bundled dynamic_credentials helper, placed in the `apikey` header. The real
key never touches this script: the runtime swaps the surrogate on approved
egress, only to <ref>.supabase.co.

HONESTY NOTE: the write endpoints and the Prefer-header semantics below are
taken from Supabase's public PostgREST docs and have not been verified in a
live flow. Per Supabase's docs, requests should carry BOTH the `apikey` and
the `Authorization: Bearer <key>` headers; this CLI keeps the skill's existing
apikey-only placement (see SKILL.md Auth). If a write 401s/403s, re-check the
connect placement and the key's validity.

Writes (insert, update, delete) require an exact --confirm string echoed by
the CLI, on every call. update/delete refuse to run without at least one
equality (`eq`) filter, so a table-wide update/delete cannot happen by
accident. WARNING: the service_role key bypasses Row Level Security: writes
are unrestricted.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.supabase"

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


def call(args, method: str, path: str, params=None, payload=None,
         prefer: str | None = None, accept: str | None = None):
    host = f"{args.project_ref}.supabase.co"
    url = f"https://{host}/rest/v1" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {}
    if accept:
        headers["Accept"] = accept
    if prefer:
        headers["Prefer"] = prefer
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=(host,))
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        sys.exit(f"error: supabase API returned HTTP {exc.code}: {body}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def parse_filters(raw_list) -> list:
    """Turn repeated --filter COLUMN=op.value flags into urlencode pairs."""
    params = []
    for raw in raw_list or []:
        if "=" not in raw:
            sys.exit(
                f"error: bad --filter {raw!r}: expected COLUMN=op.value, "
                "e.g. id=eq.123")
        col, val = raw.split("=", 1)
        col, val = col.strip(), val.strip()
        if not col or not val:
            sys.exit(f"error: bad --filter {raw!r}: column and value "
                     "are both required")
        params.append((col, val))
    return params


def require_eq_filter(params) -> None:
    """update/delete refuse without at least one equality filter."""
    if not params:
        sys.exit(
            "refusing: update/delete need at least one --filter "
            "(e.g. --filter 'id=eq.123'). Unfiltered table-wide writes "
            "are never allowed.")
    if not any(val.startswith("eq.") for _, val in params):
        sys.exit(
            "refusing: at least one --filter must be an equality filter "
            "(COLUMN=eq.VALUE). Unfiltered or range-only table-wide writes "
            "are never allowed.")


def cmd_tables(args):
    spec = call(args, "GET", "/", accept="application/openapi+json")
    tables = sorted((spec.get("definitions") or {}).keys())
    print(json.dumps(tables, indent=2))


def cmd_query(args):
    table = urllib.parse.quote(args.table, safe="")
    rows = call(args, "GET", f"/{table}",
                params={"select": "*", "limit": args.limit})
    print(json.dumps(rows, indent=2))


def cmd_insert(args):
    table = urllib.parse.quote(args.table, safe="")
    try:
        row = json.loads(args.row)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --row must be valid JSON: {exc}")
    if isinstance(row, list):
        if not row or not all(isinstance(r, dict) for r in row):
            sys.exit("error: --row array must be a non-empty list of JSON "
                     "objects")
        n = len(row)
    elif isinstance(row, dict):
        n = 1
    else:
        sys.exit("error: --row must be a JSON object or an array of JSON "
                 "objects")
    expected = f"insert {n} row(s) into {args.table}"
    need_confirm(
        args, expected,
        f"inserting {n} row(s) into table {args.table!r}. "
        "The service_role key bypasses Row Level Security: this write "
        "is unrestricted.")
    result = call(args, "POST", f"/{table}", payload=row,
                  prefer="return=representation")
    print(json.dumps({"ok": True, "table": args.table,
                      "inserted": n, "rows": result}, indent=2))


def cmd_update(args):
    table = urllib.parse.quote(args.table, safe="")
    params = parse_filters(args.filter)
    require_eq_filter(params)
    try:
        patch = json.loads(args.set)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --set must be valid JSON: {exc}")
    if not isinstance(patch, dict) or not patch:
        sys.exit("error: --set must be a non-empty JSON object")
    filt_str = "&".join(f"{c}={v}" for c, v in params)
    expected = f"update rows in {args.table} where {filt_str}"
    need_confirm(
        args, expected,
        f"updating EVERY row in table {args.table!r} matching {filt_str!r}. "
        "The service_role key bypasses Row Level Security: this write "
        "is unrestricted.")
    result = call(args, "PATCH", f"/{table}", params=params, payload=patch,
                  prefer="return=representation")
    print(json.dumps({"ok": True, "table": args.table, "filter": filt_str,
                      "updated_rows": result}, indent=2))


def cmd_delete(args):
    table = urllib.parse.quote(args.table, safe="")
    params = parse_filters(args.filter)
    require_eq_filter(params)
    filt_str = "&".join(f"{c}={v}" for c, v in params)
    expected = f"delete rows in {args.table} where {filt_str}"
    need_confirm(
        args, expected,
        f"DELETING every row in table {args.table!r} matching {filt_str!r}. "
        "This is permanent. The service_role key bypasses Row Level "
        "Security: this write is unrestricted.")
    result = call(args, "DELETE", f"/{table}", params=params,
                  prefer="return=representation")
    print(json.dumps({"ok": True, "table": args.table, "filter": filt_str,
                      "deleted_rows": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Supabase PostgREST CLI (muse-connectors)")
    parser.add_argument("--project-ref", required=True,
                        help="project ref, the <ref> in https://<ref>.supabase.co")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("tables", help="list tables in the database")
    p.set_defaults(func=cmd_tables)

    p = sub.add_parser("query", help="query rows from a table")
    p.add_argument("--table", required=True)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("insert",
                       help="insert row(s) into a table (needs --confirm)")
    p.add_argument("--table", required=True)
    p.add_argument("--row", required=True,
                   help="JSON object, or array of JSON objects, to insert")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_insert)

    p = sub.add_parser("update",
                       help="update rows matching an eq filter "
                            "(needs --confirm)")
    p.add_argument("--table", required=True)
    p.add_argument("--set", required=True,
                   help="JSON object of columns to update")
    p.add_argument("--filter", action="append", default=[],
                   help="COLUMN=op.value, repeatable; at least one eq filter "
                        "is required (e.g. --filter 'id=eq.123')")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("delete",
                       help="delete rows matching an eq filter "
                            "(needs --confirm)")
    p.add_argument("--table", required=True)
    p.add_argument("--filter", action="append", default=[],
                   help="COLUMN=op.value, repeatable; at least one eq filter "
                        "is required (e.g. --filter 'id=eq.123')")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
