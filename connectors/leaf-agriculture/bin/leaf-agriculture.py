#!/usr/bin/env python3
"""Minimal Leaf Agriculture unified farm-data CLI for the muse-connectors
leaf-agriculture skill.

Auth: loads the per-user `custom.leaf-agriculture` API key as a surrogate
via the bundled dynamic_credentials helper. Leaf authenticates with
`Authorization: Bearer <token>`; the placement is resolved by the helper
from the credential config. The real key never touches this script: the
runtime swaps the surrogate on approved egress, only to api.withleaf.io.

Safety: this connector moves farm data only; there is no direct physical
actuation. Field deletes and provider pushes still require an exact
--confirm string because they sync into connected provider platforms.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.leaf-agriculture"
ALLOWED_HOSTS = ("api.withleaf.io",)
API = "https://api.withleaf.io"
CONNECT_GUIDANCE = (
    "not connected: collect a Leaf API key (Leaf dashboard) via the secure "
    "credential flow (credentials.request_api_access) as "
    "`custom.leaf-agriculture`, then retry. Pass your Leaf user id as "
    "--user-id."
)

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


def call(method: str, service: str, path: str,
         payload: dict | None = None) -> dict:
    url = API + f"/services/{service}/api" + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        if "missing" in str(exc) or "surrogate" in str(exc):
            sys.exit(CONNECT_GUIDANCE)
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: leaf returned HTTP {exc.code}: {msg}")
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


def load_file(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        sys.exit(f"error: could not read JSON file {path}: {exc}")


def shape_field(f: dict) -> dict:
    return {"id": f.get("id"), "name": f.get("name"),
            "providers": f.get("providers"),
            "geometry": bool(f.get("geometry"))}


def cmd_auth(args):
    result = call("GET", "fields", f"/users/{args.user_id}/fields")
    fields = result if isinstance(result, list) else result.get("data", [])
    print(json.dumps({"ok": True, "fields_count": len(fields)}, indent=2))


def cmd_fields(args):
    result = call("GET", "fields", f"/users/{args.user_id}/fields")
    fields = result if isinstance(result, list) else result.get("data", [])
    print(json.dumps([shape_field(f) for f in fields], indent=2))


def cmd_field_get(args):
    f = call("GET", "fields",
             f"/users/{args.user_id}/fields/{args.field_id}")
    print(json.dumps(shape_field(f), indent=2))


def cmd_field_create(args):
    payload = load_file(args.file)
    f = call("POST", "fields", f"/users/{args.user_id}/fields", payload)
    print(json.dumps({"ok": True, "field": shape_field(f)}, indent=2))


def cmd_field_update(args):
    payload = load_file(args.file)
    f = call("PATCH", "fields",
             f"/users/{args.user_id}/fields/{args.field_id}", payload)
    print(json.dumps({"ok": True, "field": shape_field(f)}, indent=2))


def cmd_field_delete(args):
    expected = f"delete field {args.field_id}"
    need_confirm(
        args, expected,
        "deleting a field removes the record in Leaf and syncs to connected "
        "providers.")
    call("DELETE", "fields", f"/users/{args.user_id}/fields/{args.field_id}")
    print(json.dumps({"ok": True, "deleted": args.field_id}, indent=2))


def cmd_field_sync(args):
    result = call("POST", "fields", f"/users/{args.user_id}/fields/sync")
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_field_push(args):
    expected = f"push field {args.field_id} to {args.provider}"
    need_confirm(
        args, expected,
        "pushing field data into a provider (e.g. John Deere Operations "
        "Center) puts boundaries/prescriptions where equipment or operators "
        "may act on them.")
    provider = urllib.parse.quote(args.provider, safe="")
    result = call("POST", "fields",
                  f"/users/{args.user_id}/fields/{args.field_id}/"
                  f"integration/{provider}")
    print(json.dumps({"ok": True, "provider": args.provider,
                      "result": result}, indent=2))


def cmd_operation_files(args):
    result = call("GET", "fields",
                  f"/users/{args.user_id}/fields/{args.field_id}/"
                  f"operations/files")
    files = result if isinstance(result, list) else result.get("data", [])
    out = [{"id": o.get("id"), "operation_type": o.get("operationType"),
            "provider": o.get("provider"),
            "start_date": o.get("startDate"), "end_date": o.get("endDate")}
           for o in files]
    print(json.dumps(out, indent=2))


def cmd_irrigation(args):
    result = call("GET", "irrigation",
                  f"/users/{args.user_id}/irrigation/applied-irrigation")
    events = result if isinstance(result, list) else result.get("data", [])
    out = [{"id": e.get("id"), "field_id": e.get("fieldId"),
            "provider": e.get("provider"),
            "start_date": e.get("startDate"), "end_date": e.get("endDate"),
            "amount": e.get("amount")}
           for e in events]
    print(json.dumps(out, indent=2))


def add_user(p):
    p.add_argument("--user-id", required=True,
                   help="Leaf user id (from the Leaf dashboard)")


def main():
    parser = argparse.ArgumentParser(
        description="Leaf Agriculture farm-data CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    add_user(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("fields", help="list fields")
    add_user(p)
    p.set_defaults(func=cmd_fields)

    p = sub.add_parser("field-get", help="retrieve one field")
    add_user(p)
    p.add_argument("--field-id", required=True)
    p.set_defaults(func=cmd_field_get)

    p = sub.add_parser("field-create", help="create a field record")
    add_user(p)
    p.add_argument("--file", required=True,
                   help="JSON file with the field payload")
    p.set_defaults(func=cmd_field_create)

    p = sub.add_parser("field-update", help="update a field record")
    add_user(p)
    p.add_argument("--field-id", required=True)
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_field_update)

    p = sub.add_parser("field-delete", help="delete a field record")
    add_user(p)
    p.add_argument("--field-id", required=True)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_field_delete)

    p = sub.add_parser("field-sync", help="trigger a manual field sync")
    add_user(p)
    p.set_defaults(func=cmd_field_sync)

    p = sub.add_parser("field-push", help="push field data into a provider")
    add_user(p)
    p.add_argument("--field-id", required=True)
    p.add_argument("--provider", required=True,
                   help="e.g. john-deere, cnhi, climate-fieldview, trimble, "
                        "raven, agleader")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_field_push)

    p = sub.add_parser("operation-files",
                       help="machine operation files for a field")
    add_user(p)
    p.add_argument("--field-id", required=True)
    p.set_defaults(func=cmd_operation_files)

    p = sub.add_parser("irrigation", help="as-applied irrigation events")
    add_user(p)
    p.set_defaults(func=cmd_irrigation)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
