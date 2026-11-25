#!/usr/bin/env python3
"""Minimal Attio API CLI for the muse-connectors attio skill.

Auth: loads the per-user `custom.attio` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.attio.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.attio"
ALLOWED_HOSTS = ("api.attio.com",)
API = "https://api.attio.com/v2"

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
        sys.exit(f"error: attio returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = call("GET", "/objects", params={"limit": 1})
    objects = result.get("data", [])
    print(json.dumps({"ok": True, "objects": len(objects),
                      "first": objects[0].get("api_slug") if objects else None},
                     indent=2))


def cmd_objects(_args):
    result = call("GET", "/objects")
    objects = [
        {"api_slug": o.get("api_slug"), "singular": o.get("singular_noun"),
         "plural": o.get("plural_noun")}
        for o in result.get("data", [])
    ]
    print(json.dumps(objects, indent=2))


def cmd_query(args):
    try:
        body = json.loads(args.filter_json)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --filter-json is not valid JSON: {exc}")
    result = call("POST", f"/objects/{args.object_slug}/records/query",
                  payload=body)
    records = result.get("data", [])
    out = [
        {"id": r.get("id", {}).get("record_id"),
         "values": r.get("values")}
        for r in records
    ]
    print(json.dumps(out, indent=2))


def cmd_upsert(args):
    try:
        values = json.loads(args.values_json)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --values-json is not valid JSON: {exc}")
    payload = {"data": {"matching_attribute": args.match_attribute,
                        "values": values}}
    result = call("PUT", f"/objects/{args.object_slug}/records",
                  payload=payload)
    record = result.get("data", {})
    print(json.dumps({"ok": True,
                      "id": (record.get("id") or {}).get("record_id"),
                      "values": record.get("values")}, indent=2))


def cmd_note(args):
    payload = {"data": {"record_id": args.record_id,
                        "title": args.title, "content": args.content}}
    result = call("POST", "/notes", payload=payload)
    note = result.get("data", {})
    print(json.dumps({"ok": True,
                      "id": (note.get("id") or {}).get("note_id")}, indent=2))


def cmd_task(args):
    payload = {"data": {"record_id": args.record_id,
                        "title": args.title}}
    result = call("POST", "/tasks", payload=payload)
    task = result.get("data", {})
    print(json.dumps({"ok": True,
                      "id": (task.get("id") or {}).get("task_id")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Attio API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("objects", help="list available objects")
    p.set_defaults(func=cmd_objects)

    p = sub.add_parser("query", help="query records on an object")
    p.add_argument("--object-slug", required=True, help="e.g. companies")
    p.add_argument("--filter-json", required=True,
                   help='query body, e.g. \'{"filters":[{"property":"email",'
                        '"condition":"equals","value":"a@acme.com"}]}\'')
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("upsert", help="create or update a record (confirm first)")
    p.add_argument("--object-slug", required=True, help="e.g. companies")
    p.add_argument("--match-attribute", required=True,
                   help="attribute used to match an existing record, e.g. email")
    p.add_argument("--values-json", required=True,
                   help='attribute values, e.g. \'{"name":[{"value":"Acme"}],'
                        '"email":[{"value":"a@acme.com"}]}\'')
    p.set_defaults(func=cmd_upsert)

    p = sub.add_parser("note", help="add a note to a record (confirm first)")
    p.add_argument("--record-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--content", required=True)
    p.set_defaults(func=cmd_note)

    p = sub.add_parser("task", help="add a task to a record (confirm first)")
    p.add_argument("--record-id", required=True)
    p.add_argument("--title", required=True)
    p.set_defaults(func=cmd_task)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
