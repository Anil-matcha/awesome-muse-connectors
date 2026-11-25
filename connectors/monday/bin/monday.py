#!/usr/bin/env python3
"""Minimal monday.com API CLI for the muse-connectors Monday skill.

Auth: loads the per-user `custom.monday` credential as a surrogate via the
bundled dynamic_credentials helper. monday.com takes the raw personal API token
as the `Authorization` header value (no Bearer prefix); the placement is
resolved by the helper from the credential config. The real token never touches
this script: the runtime swaps the surrogate on approved egress, only to
api.monday.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.monday"
ALLOWED_HOSTS = ("api.monday.com",)
API = "https://api.monday.com/v2"

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


def graphql(query: str, variables: dict | None = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API, data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = read_json_response(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: monday returned HTTP {exc.code}: "
                 f"{exc.read().decode('utf-8', errors='replace')[:300]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if result.get("errors"):
        sys.exit(f"error: monday GraphQL error: {json.dumps(result['errors'])}")
    return result.get("data", {})


def cmd_auth(_args):
    data = graphql("{ me { id name email } }")
    print(json.dumps({"ok": True, "me": data.get("me")}, indent=2))


def cmd_boards(args):
    data = graphql(
        "query($limit: Int) { boards(limit: $limit) { id name board_kind state } }",
        {"limit": args.limit})
    print(json.dumps(data.get("boards", []), indent=2))


def cmd_items(args):
    data = graphql(
        """query($boardId: [ID!], $limit: Int) {
             boards(ids: $boardId) {
               items_page(limit: $limit) {
                 items { id name group { title }
                         column_values { id text } } } } }""",
        {"boardId": args.board, "limit": args.limit})
    boards = data.get("boards", [])
    items = (boards[0].get("items_page", {}).get("items", []) if boards else [])
    print(json.dumps(items, indent=2))


def cmd_create_item(args):
    data = graphql(
        """mutation($boardId: ID!, $name: String!) {
             create_item(board_id: $boardId, item_name: $name) { id name } }""",
        {"boardId": args.board, "name": args.name})
    print(json.dumps({"ok": True, "item": data.get("create_item")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="monday.com API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("boards", help="list boards")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_boards)

    p = sub.add_parser("items", help="list items on a board")
    p.add_argument("--board", required=True, help="board ID")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_items)

    p = sub.add_parser("create-item", help="create an item on a board (confirm first)")
    p.add_argument("--board", required=True, help="board ID")
    p.add_argument("--name", required=True, help="item name")
    p.set_defaults(func=cmd_create_item)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
