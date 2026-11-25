#!/usr/bin/env python3
"""Minimal Readwise API CLI for the muse-connectors Readwise skill.

Auth: loads the per-user `custom.readwise` credential as a surrogate via the
bundled dynamic_credentials helper. Readwise expects the non-standard header
`Authorization: Token <key>`, so the CLI builds that header from the surrogate
itself (only the `hsurr:*` placeholder ever appears here; the runtime swaps in
the real key on approved egress, only to readwise.io).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.readwise"
ALLOWED_HOSTS = ("readwise.io",)
API = "https://readwise.io/api/v2"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        dynamic_credential_entry,
        ensure_allowed_url,
        read_json_response,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def auth_headers(url: str) -> dict:
    ensure_allowed_url(url, ALLOWED_HOSTS)
    try:
        entry = dynamic_credential_entry(CREDENTIAL_NAME)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    surrogate = str(entry["surrogate"]).strip()
    return {"Authorization": f"Token {surrogate}"}


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None):
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    headers.update(auth_headers(url))
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 204:
                return {"ok": True}
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 204:
            return {"ok": True}
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("detail", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: readwise returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    call("GET", "/auth/")
    print(json.dumps({"ok": True}, indent=2))


def cmd_books(args):
    result = call("GET", "/books/", params={"page_size": args.limit})
    books = [
        {"id": b["id"], "title": b.get("title"), "author": b.get("author"),
         "category": b.get("category"), "num_highlights": b.get("num_highlights")}
        for b in result.get("results", [])
    ]
    print(json.dumps(books, indent=2))


def cmd_highlights(args):
    params = {"page_size": args.limit}
    if args.book:
        params["book_id"] = args.book
    result = call("GET", "/highlights/", params=params)
    highlights = [
        {"id": h["id"], "text": h.get("text"), "note": h.get("note"),
         "book_id": h.get("book_id"), "highlighted_at": h.get("highlighted_at")}
        for h in result.get("results", [])
    ]
    print(json.dumps(highlights, indent=2))


def cmd_add(args):
    highlight = {"text": args.text}
    if args.title:
        highlight["title"] = args.title
    if args.author:
        highlight["author"] = args.author
    if args.note:
        highlight["note"] = args.note
    result = call("POST", "/highlights/", payload={"highlights": [highlight]})
    added = result[0] if isinstance(result, list) and result else result
    print(json.dumps({"ok": True, "id": (added or {}).get("id")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Readwise API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("books", help="list books in the library")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_books)

    p = sub.add_parser("highlights", help="list highlights")
    p.add_argument("--book", default=None, help="filter to one book ID")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_highlights)

    p = sub.add_parser("add", help="save a highlight (confirm first)")
    p.add_argument("--text", required=True)
    p.add_argument("--title", default=None)
    p.add_argument("--author", default=None)
    p.add_argument("--note", default=None)
    p.set_defaults(func=cmd_add)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
