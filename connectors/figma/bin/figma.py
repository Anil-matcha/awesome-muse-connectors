#!/usr/bin/env python3
"""Minimal Figma REST API CLI for the muse-connectors Figma skill.

Auth: loads the per-user `custom.figma` credential as a surrogate via the
bundled dynamic_credentials helper. The real token never touches this script:
the runtime swaps the surrogate on approved egress, only to api.figma.com.

HONESTY NOTE: the POST /v1/files/{file_key}/comments endpoint and its
`message` body field are taken from Figma's public REST API docs and have not
been verified in a live flow. The `client_meta` shape used for anchored
comments ({node_id}) is taken from community docs of the Figma API, not the
official reference, and has not been verified live: plain --x/--y canvas
pinning is therefore not supported, only node anchoring. Posting a comment
needs a token with the `file_comments:write` scope.
Comment posts require an exact --confirm string echoed by the CLI, on every
call.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.figma"
ALLOWED_HOSTS = ("api.figma.com",)
API = "https://api.figma.com/v1"

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


def call(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
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
            detail = json.loads(body).get("message", body)
        except Exception:
            detail = str(exc)
        sys.exit(f"error: figma returned HTTP {exc.code}: {detail}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    return result


def cmd_me(_args):
    result = call("/me")
    print(json.dumps(
        {"id": result.get("id"), "handle": result.get("handle"),
         "email": result.get("email")},
        indent=2))


def cmd_file(args):
    # Intentionally metadata-only: the full document payload is huge.
    result = call(f"/files/{args.key}")
    print(json.dumps(
        {"name": result.get("name"), "lastModified": result.get("lastModified"),
         "version": result.get("version"),
         "thumbnailUrl": result.get("thumbnailUrl")},
        indent=2))


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def cmd_comment(args):
    key = urllib.parse.quote(args.key, safe="")
    payload = {"message": args.message}
    if args.node_id:
        # HONESTY NOTE: client_meta shape taken from community docs of the
        # Figma API, not the official reference; not verified in a live flow.
        payload["client_meta"] = {"node_id": args.node_id}
    expected = f'post comment on file {args.key}: "{args.message}"'
    need_confirm(
        args, expected,
        f"posting a comment to Figma file {args.key!r} as the authenticated "
        "user (visible to file collaborators).")
    result = call(f"/files/{key}/comments", method="POST", payload=payload)
    print(json.dumps(
        {"ok": True, "id": result.get("id"),
         "message": result.get("message"),
         "created_at": result.get("created_at")},
        indent=2))


def main():
    parser = argparse.ArgumentParser(description="Figma REST API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("me", help="authenticated user")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("file", help="file metadata (name, lastModified, version, thumbnailUrl)")
    p.add_argument("--key", required=True, help="file key from the Figma URL")
    p.set_defaults(func=cmd_file)

    p = sub.add_parser("comment",
                       help="post a comment on a file (needs --confirm)")
    p.add_argument("--key", required=True, help="file key from the Figma URL")
    p.add_argument("--message", required=True, help="comment text")
    p.add_argument("--node-id", default=None,
                   help="optional node id (e.g. 1:42) to anchor the comment "
                        "to a node")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_comment)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
