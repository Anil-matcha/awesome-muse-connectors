#!/usr/bin/env python3
"""Minimal Notion API CLI for the muse-connectors Notion skill.

Auth: loads the per-user `custom.notion` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api.notion.com.
Every request also carries the required Notion-Version header.

Reads (search, page, query-db) need no confirmation. Writes
(page-create, block-append, page-update) require an exact --confirm string
echoed by the CLI, on every call.
HONESTY NOTE: the write endpoint paths and bodies below are taken from
Notion's public API docs and have not yet been verified in a live flow.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.notion"
ALLOWED_HOSTS = ("api.notion.com",)
API = "https://api.notion.com"
NOTION_VERSION = "2022-06-28"
CONNECT_GUIDANCE = (
    "not connected: approve Notion access via the secure credential flow "
    "(credentials.request_api_access) as `custom.notion` (create an internal "
    "integration at notion.so/my-integrations and share the needed "
    "pages/databases with it inside Notion), then retry."
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


def call(method: str, path: str, payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {"Notion-Version": NOTION_VERSION}
    if payload is not None or method in ("POST", "PATCH"):
        data = json.dumps(payload or {}).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        if "missing" in str(exc) or "surrogate" in str(exc):
            sys.exit(CONNECT_GUIDANCE)
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = f"{body.get('code')}: {body.get('message')}"
        except Exception:
            msg = str(exc)
        sys.exit(f"error: notion returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    return result


def plain_text(rich: object) -> str:
    if isinstance(rich, list):
        return "".join(item.get("plain_text", "") for item in rich if isinstance(item, dict))
    return ""


def flatten_property(prop: dict) -> object:
    ptype = prop.get("type")
    value = prop.get(ptype) if isinstance(ptype, str) else None
    if ptype in ("title", "rich_text"):
        return plain_text(value)
    if ptype in ("number", "checkbox", "url", "email", "phone_number"):
        return value
    if ptype == "select":
        return (value or {}).get("name") if isinstance(value, dict) else None
    if ptype == "multi_select":
        return [v.get("name") for v in value] if isinstance(value, list) else []
    if ptype == "status":
        return (value or {}).get("name") if isinstance(value, dict) else None
    if ptype == "date":
        return (value or {}).get("start") if isinstance(value, dict) else None
    if ptype == "people":
        return [p.get("name") for p in value] if isinstance(value, list) else []
    return str(value)[:120] if value is not None else None


def cmd_auth(_args):
    result = call("POST", "/v1/search", {"page_size": 1})
    print(json.dumps({"ok": True, "results": len(result.get("results", []))}, indent=2))


def summarize_object(obj: dict) -> dict:
    out = {"object": obj.get("object"), "id": obj.get("id")}
    props = obj.get("properties")
    if isinstance(props, dict):
        out["properties"] = {k: flatten_property(v) for k, v in props.items()
                              if isinstance(v, dict)}
    title_prop = None
    if isinstance(props, dict):
        for v in props.values():
            if isinstance(v, dict) and v.get("type") == "title":
                title_prop = flatten_property(v)
                break
    if title_prop:
        out["title"] = title_prop
    return out


def cmd_search(args):
    payload = {"page_size": 20}
    if args.query:
        payload["query"] = args.query
    result = call("POST", "/v1/search", payload)
    print(json.dumps([summarize_object(o) for o in result.get("results", [])], indent=2))


def cmd_page(args):
    result = call("GET", f"/v1/pages/{args.id}")
    print(json.dumps(summarize_object(result), indent=2))


def cmd_query_db(args):
    result = call("POST", f"/v1/databases/{args.id}/query", {"page_size": 20})
    rows = []
    for page in result.get("results", []):
        props = page.get("properties", {})
        rows.append({"id": page.get("id"),
                     **{k: flatten_property(v) for k, v in props.items()
                        if isinstance(v, dict)}})
    print(json.dumps(rows, indent=2))


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def _json_obj(raw: str, flag: str) -> dict:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: {flag} is not valid JSON: {exc}")
    if not isinstance(obj, dict):
        sys.exit(f"error: {flag} must be a JSON object")
    return obj


def cmd_page_create(args):
    props = _json_obj(args.properties, "--properties")
    if args.parent_type == "database":
        parent = {"database_id": args.parent_id}
    else:
        parent = {"page_id": args.parent_id}
    expected = f"create notion page under {args.parent_type} {args.parent_id}"
    need_confirm(
        args, expected,
        f"creating a new Notion page under {args.parent_type} {args.parent_id}.")
    result = call("POST", "/v1/pages",
                  {"parent": parent, "properties": props})
    print(json.dumps({"ok": True, "page_id": result.get("id"),
                      "url": result.get("url")}, indent=2))


def cmd_block_append(args):
    try:
        blocks = json.loads(args.blocks)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --blocks is not valid JSON: {exc}")
    if not isinstance(blocks, list) or not blocks:
        sys.exit("error: --blocks must be a non-empty JSON array of block objects")
    expected = f"append {len(blocks)} block(s) to {args.block_id}"
    need_confirm(
        args, expected,
        f"appending {len(blocks)} block(s) to Notion block/page {args.block_id}.")
    result = call("PATCH", f"/v1/blocks/{args.block_id}/children",
                  {"children": blocks})
    appended = result.get("results", [])
    print(json.dumps({"ok": True, "appended": len(appended),
                      "block_ids": [b.get("id") for b in appended]},
                     indent=2))


def cmd_page_update(args):
    props = _json_obj(args.properties, "--properties")
    expected = f"update notion page {args.id} properties"
    need_confirm(
        args, expected,
        f"updating properties on Notion page {args.id}.")
    result = call("PATCH", f"/v1/pages/{args.id}", {"properties": props})
    print(json.dumps({"ok": True, "page_id": result.get("id")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Notion API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("search", help="search pages and databases")
    p.add_argument("--query", default="")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("page", help="read a page's properties")
    p.add_argument("--id", required=True, help="page ID")
    p.set_defaults(func=cmd_page)

    p = sub.add_parser("query-db", help="query a database (first 20 rows)")
    p.add_argument("--id", required=True, help="database ID")
    p.set_defaults(func=cmd_query_db)

    p = sub.add_parser("page-create",
                       help="create a page (needs --confirm)")
    p.add_argument("--parent-id", required=True,
                   help="parent page or database ID")
    p.add_argument("--parent-type", default="page",
                   choices=("page", "database"),
                   help="whether --parent-id is a page or a database")
    p.add_argument("--properties", required=True,
                   help='JSON object of Notion API properties, e.g. \'{"title": {"title": [{"text": {"content": "Note"}}]}}\'')
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_page_create)

    p = sub.add_parser("block-append",
                       help="append blocks to a page/block (needs --confirm)")
    p.add_argument("--block-id", required=True,
                   help="page or block ID to append under")
    p.add_argument("--blocks", required=True,
                   help="JSON array of Notion block objects")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_block_append)

    p = sub.add_parser("page-update",
                       help="update a page's properties (needs --confirm)")
    p.add_argument("--id", required=True, help="page ID")
    p.add_argument("--properties", required=True,
                   help="JSON object of Notion API properties to set")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_page_update)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
