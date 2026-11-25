#!/usr/bin/env python3
"""Minimal X API v2 CLI for the muse-connectors x skill.

Auth: loads the per-user `custom.x` OAuth token as a surrogate via the
bundled dynamic_credentials helper (OAuth2 PKCE, same pattern as the slack
connector). The real token never touches this script: the runtime swaps the
surrogate on approved egress, only to api.x.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.x"
ALLOWED_HOSTS = ("api.x.com",)
API = "https://api.x.com"

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
            msg = body.get("detail", body.get("title", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: X returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def me_id() -> str:
    """Resolve the authenticated user's numeric ID via /2/users/me."""
    result = call("GET", "/2/users/me")
    user_id = (result.get("data") or {}).get("id")
    if not user_id:
        sys.exit("error: could not resolve the authenticated user ID")
    return user_id


def cmd_auth(_args):
    result = call("GET", "/2/users/me")
    user = result.get("data", {})
    print(json.dumps({"ok": True, "id": user.get("id"),
                      "username": user.get("username")}, indent=2))


def cmd_post(args):
    result = call("POST", "/2/tweets", payload={"text": args.text})
    data = result.get("data", {})
    print(json.dumps({"ok": True, "id": data.get("id"),
                      "text": data.get("text")}, indent=2))


def cmd_search(args):
    params = {"query": args.query}
    if args.limit:
        params["max_results"] = args.limit
    result = call("GET", "/2/tweets/search/recent", params=params)
    tweets = [
        {"id": t.get("id"), "text": t.get("text"),
         "created_at": t.get("created_at")}
        for t in result.get("data", [])
    ]
    print(json.dumps(tweets, indent=2))


def cmd_like(args):
    user_id = me_id()
    call("POST", f"/2/users/{user_id}/likes",
         payload={"tweet_id": args.tweet_id})
    print(json.dumps({"ok": True, "tweet_id": args.tweet_id,
                      "liked_by": user_id}, indent=2))


def cmd_dm(args):
    result = call("POST", "/2/dm_conversations",
                  payload={"participant_id": args.user_id,
                           "text": args.text})
    convo = result.get("data", {})
    print(json.dumps({"ok": True, "dm_conversation_id": convo.get("id")},
                     indent=2))


def cmd_delete(args):
    result = call("DELETE", f"/2/tweets/{args.tweet_id}")
    data = result.get("data", {})
    print(json.dumps({"ok": True, "deleted": data.get("deleted"),
                      "tweet_id": args.tweet_id}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="X API v2 CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the OAuth token")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("post", help="post a tweet (confirm first)")
    p.add_argument("--text", required=True, help="tweet text")
    p.set_defaults(func=cmd_post)

    p = sub.add_parser("search", help="search recent tweets")
    p.add_argument("--query", required=True, help="search query")
    p.add_argument("--limit", type=int, default=10,
                   help="max results (10-100)")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("like", help="like a tweet (confirm first)")
    p.add_argument("--tweet-id", required=True)
    p.set_defaults(func=cmd_like)

    p = sub.add_parser("dm", help="send a DM (confirm first)")
    p.add_argument("--user-id", required=True,
                   help="recipient's numeric user ID")
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_dm)

    p = sub.add_parser("delete", help="delete a tweet (confirm first)")
    p.add_argument("--tweet-id", required=True)
    p.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
