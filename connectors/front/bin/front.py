#!/usr/bin/env python3
"""Minimal Front Core API CLI for the muse-connectors Front skill.

Auth: loads the per-user `custom.front` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api2.frontapp.com.

Reads (inboxes, conversations, teammates) need no confirmation. Writes
(reply, assign, tag) require an exact --confirm string echoed by the CLI,
on every call.
HONESTY NOTE: the write endpoint paths and bodies below are taken from
Front's public developer docs (dev.frontapp.com reference pages) and have
not yet been verified in a live flow. Note the reply scope (`messages:send`)
and conversation-update scope (`conversations:write`) needed on the token.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.front"
ALLOWED_HOSTS = ("api2.frontapp.com",)
API = "https://api2.frontapp.com"
CONNECT_GUIDANCE = (
    "not connected: approve Front access via the secure credential flow "
    "(credentials.request_api_access) as `custom.front` (create a token in "
    "Front -> Settings -> API with messages:send and conversations:write "
    "scopes), then retry."
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


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {}
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
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return {}  # e.g. PATCH update returns 204 No content
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            detail = json.loads(body).get("message", body)
        except Exception:
            detail = str(exc)
        sys.exit(f"error: front returned HTTP {exc.code}: {detail}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_inboxes(_args):
    result = call("GET", "/inboxes")
    inboxes = [
        {"id": i.get("id"), "name": i.get("name"), "address": i.get("address")}
        for i in result.get("_results", [])
    ]
    print(json.dumps(inboxes, indent=2))


def cmd_conversations(args):
    result = call("GET", f"/inboxes/{args.inbox}/conversations",
                  params={"limit": args.limit})
    convs = [
        {"id": c.get("id"), "subject": c.get("subject"), "status": c.get("status"),
         "created_at": c.get("created_at")}
        for c in result.get("_results", [])
    ]
    print(json.dumps(convs, indent=2))


def cmd_teammates(_args):
    result = call("GET", "/teammates")
    teammates = [
        {"id": t.get("id"), "name": " ".join(x for x in
              (t.get("first_name"), t.get("last_name")) if x),
         "email": t.get("email"), "username": t.get("username")}
        for t in result.get("_results", [])
    ]
    print(json.dumps(teammates, indent=2))


def cmd_reply(args):
    to = [h.strip() for h in args.to.split(",") if h.strip()]
    if not to:
        sys.exit("error: --to needs at least one recipient handle")
    body = args.body
    expected = f"reply to {args.conversation} with {len(body)} chars"
    need_confirm(
        args, expected,
        f"sending a reply in conversation {args.conversation} to {', '.join(to)}.")
    payload = {"to": to, "body": body}
    if args.subject:
        payload["subject"] = args.subject
    if args.author_id:
        payload["author_id"] = args.author_id
    if args.cc:
        payload["cc"] = [h.strip() for h in args.cc.split(",") if h.strip()]
    result = call("POST", f"/conversations/{args.conversation}/messages",
                  payload=payload)
    print(json.dumps({"ok": True, "message_id": result.get("id"),
                      "conversation": args.conversation,
                      "to": to}, indent=2))


def cmd_assign(args):
    if args.unassign:
        expected = f"unassign {args.conversation}"
        need_confirm(
            args, expected,
            f"removing the assignee from conversation {args.conversation}.")
        payload = {"assignee_id": None}
    else:
        if not args.teammate:
            sys.exit("error: pass --teammate TEA_ID or --unassign")
        expected = f"assign {args.conversation} to {args.teammate}"
        need_confirm(
            args, expected,
            f"assigning conversation {args.conversation} to teammate "
            f"{args.teammate}.")
        payload = {"assignee_id": args.teammate}
    call("PATCH", f"/conversations/{args.conversation}", payload=payload)
    print(json.dumps({"ok": True, "conversation": args.conversation,
                      "assignee": None if args.unassign else args.teammate},
                     indent=2))


def _existing_tag_ids(conversation_id: str) -> list:
    """Best-effort read of the conversation's current tag ids.

    HONESTY NOTE: Front's docs define tag_ids as "List of all the tag IDs
    replacing the old conversation tags", so tag merges the new ids with the
    current ones read here. The read shape was not verified live; if it comes
    back empty the update passes only the new ids.
    """
    convo = call("GET", f"/conversations/{conversation_id}")
    tags = convo.get("tags") or []
    ids = []
    for t in tags:
        if isinstance(t, dict) and t.get("id"):
            ids.append(t["id"])
        elif isinstance(t, str):
            ids.append(t)
    return ids


def cmd_tag(args):
    new_ids = [t.strip() for t in args.tags.split(",") if t.strip()]
    if not new_ids:
        sys.exit("error: --tags needs at least one tag ID")
    current = _existing_tag_ids(args.conversation)
    merged = list(dict.fromkeys(current + new_ids))  # dedupe, keep order
    added = [t for t in new_ids if t not in current]
    expected = (f"add {len(added)} tag(s) to {args.conversation} "
                f"({len(merged)} total)")
    need_confirm(
        args, expected,
        f"setting tags on conversation {args.conversation} "
        f"(Front's API replaces all tags; merging {len(added)} new with "
        f"{len(current)} existing).")
    call("PATCH", f"/conversations/{args.conversation}",
         payload={"tag_ids": merged})
    print(json.dumps({"ok": True, "conversation": args.conversation,
                      "tag_ids": merged}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Front Core API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inboxes", help="list inboxes")
    p.set_defaults(func=cmd_inboxes)

    p = sub.add_parser("conversations", help="recent conversations in an inbox")
    p.add_argument("--inbox", required=True, help="inbox id, e.g. inb_123")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_conversations)

    p = sub.add_parser("teammates", help="list teammates (id, name, email)")
    p.set_defaults(func=cmd_teammates)

    p = sub.add_parser("reply",
                       help="reply to a conversation (needs --confirm)")
    p.add_argument("--conversation", required=True, help="conversation id, e.g. cnv_123")
    p.add_argument("--to", required=True,
                   help="comma-separated recipient handles (emails)")
    p.add_argument("--body", required=True,
                   help="message body (HTML for email channels)")
    p.add_argument("--subject", default=None)
    p.add_argument("--author-id", default=None,
                   help="teammate id sent on behalf of")
    p.add_argument("--cc", default=None,
                   help="comma-separated recipient handles")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_reply)

    p = sub.add_parser("assign",
                       help="assign a teammate (needs --confirm)")
    p.add_argument("--conversation", required=True, help="conversation id, e.g. cnv_123")
    p.add_argument("--teammate", default=None,
                   help="teammate id, e.g. tea_123 (use `teammates` to look up)")
    p.add_argument("--unassign", action="store_true",
                   help="remove the assignee instead")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_assign)

    p = sub.add_parser("tag",
                       help="add tags to a conversation (needs --confirm)")
    p.add_argument("--conversation", required=True, help="conversation id, e.g. cnv_123")
    p.add_argument("--tags", required=True,
                   help="comma-separated tag IDs to add")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_tag)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
