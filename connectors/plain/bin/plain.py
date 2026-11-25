#!/usr/bin/env python3
"""Minimal Plain GraphQL CLI for the muse-connectors plain skill.

Auth: loads the per-user `custom.plain` credential (a Machine User API key)
as a surrogate via the bundled dynamic_credentials helper. The real key
never touches this script: the runtime swaps the surrogate on approved
egress, only to core-api.uk.plain.com.

Every operation goes to the single GraphQL endpoint as
{"query": ..., "variables": {...}}. Field selection is conservative and the
CLI parses defensively; the full schema is published at
https://core-api.uk.plain.com/graphql/v1/schema.graphql
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.plain"
ALLOWED_HOSTS = ("core-api.uk.plain.com",)
API = "https://core-api.uk.plain.com/graphql/v1"

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
    payload = {"query": query, "variables": variables or {}}
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
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = str(body.get("errors", body.get("error", str(exc))))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: plain returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if result.get("errors"):
        sys.exit(f"error: plain GraphQL error: {result['errors']}")
    return result.get("data", {})


def edges_of(data: dict, key: str) -> list:
    return ((data.get(key) or {}).get("edges")) or []


def cmd_auth(_args):
    data = graphql("query { __typename }")
    print(json.dumps({"ok": True, "typename": data.get("__typename")},
                     indent=2))


def cmd_customer_find(args):
    data = graphql(
        "query($emails: [String!]!) { "
        "customers(filters: {emails: $emails}) { "
        "edges { node { id } } } }",
        {"emails": [args.email]},
    )
    out = [{"id": (e.get("node") or {}).get("id")}
           for e in edges_of(data, "customers")]
    print(json.dumps(out, indent=2))


def cmd_threads(args):
    data = graphql(
        "query($first: Int) { threads(first: $first) { "
        "edges { node { id } } "
        "pageInfo { hasNextPage endCursor } } }",
        {"first": args.limit},
    )
    threads = edges_of(data, "threads")
    out = [{"id": (e.get("node") or {}).get("id")} for e in threads]
    print(json.dumps({"threads": out,
                      "pageInfo": (data.get("threads") or {}).get("pageInfo")},
                     indent=2))


def cmd_customer_upsert(args):
    variables = {"email": args.email}
    if args.name:
        variables["fullName"] = args.name
    data = graphql(
        "mutation($email: String!, $fullName: String) { "
        "upsertCustomer(email: $email, fullName: $fullName) { id } }",
        variables,
    )
    customer = data.get("upsertCustomer") or {}
    print(json.dumps({"ok": True, "id": customer.get("id"),
                      "email": args.email}, indent=2))


def cmd_thread_create(args):
    data = graphql(
        "mutation($customerId: ID!, $title: String!, $text: String!) { "
        "createThread(customerId: $customerId, title: $title, text: $text) "
        "{ id } }",
        {"customerId": args.customer_id, "title": args.title,
         "text": args.text},
    )
    thread = data.get("createThread") or {}
    print(json.dumps({"ok": True, "id": thread.get("id")}, indent=2))


def cmd_thread_reply(args):
    data = graphql(
        "mutation($threadId: ID!, $text: String!) { "
        "replyToThread(threadId: $threadId, text: $text) { id } }",
        {"threadId": args.thread_id, "text": args.text},
    )
    reply = data.get("replyToThread") or {}
    print(json.dumps({"ok": True, "id": reply.get("id"),
                      "thread_id": args.thread_id}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Plain GraphQL CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the Machine User API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("customer-find", help="find a customer by email")
    p.add_argument("--email", required=True)
    p.set_defaults(func=cmd_customer_find)

    p = sub.add_parser("threads", help="list threads (paginated)")
    p.add_argument("--limit", type=int, default=25,
                   help="page size, max 100")
    p.set_defaults(func=cmd_threads)

    p = sub.add_parser("customer-upsert",
                       help="create or update a customer (confirm first)")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default=None)
    p.set_defaults(func=cmd_customer_upsert)

    p = sub.add_parser("thread-create",
                       help="open a support thread (confirm first)")
    p.add_argument("--customer-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_thread_create)

    p = sub.add_parser("thread-reply",
                       help="reply to a support thread (confirm first)")
    p.add_argument("--thread-id", required=True)
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_thread_reply)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
