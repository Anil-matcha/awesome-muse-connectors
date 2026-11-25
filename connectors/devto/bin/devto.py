#!/usr/bin/env python3
"""Minimal dev.to API CLI for the muse-connectors devto skill.

Auth: loads the per-user `custom.devto` personal API key as a surrogate via
the bundled dynamic_credentials helper. The key is sent as a PLAIN
`api-key: <key>` header (verbatim, NOT Bearer), exactly as dev.to documents.
Public reads (articles-by-user) need no key, so that subcommand never loads
the credential.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.devto"
ALLOWED_HOSTS = ("dev.to",)
API = "https://dev.to/api"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        dynamic_credential_entry,
        ensure_allowed_url,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None, authed: bool = True) -> object:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    if authed:
        try:
            surrogate = dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]
        except DynamicCredentialError as exc:
            sys.exit(f"error: credential problem: {exc}")
        # dev.to wants the key in a plain `api-key` header, not Bearer.
        req.add_header("api-key", surrogate)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: dev.to returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def article_summary(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "title": a.get("title"),
        "url": a.get("url"),
        "published": a.get("published"),
        "published_at": a.get("published_at"),
        "tags": a.get("tag_list") or a.get("tags"),
        "page_views_count": a.get("page_views_count"),
        "positive_reactions_count": a.get("positive_reactions_count"),
        "comments_count": a.get("comments_count"),
    }


def cmd_me(_args):
    me = call("GET", "/users/me")
    if not isinstance(me, dict):
        sys.exit("error: unexpected response from dev.to")
    print(json.dumps({
        "ok": True,
        "name": me.get("name"),
        "username": me.get("username"),
        "github_username": me.get("github_username"),
        "twitter_username": me.get("twitter_username"),
        "summary": (me.get("summary") or "")[:200],
    }, indent=2))


def cmd_my_articles(args):
    result = call("GET", f"/articles/me/{args.state}",
                  params={"page": args.page, "per_page": args.per_page})
    articles = result if isinstance(result, list) else []
    print(json.dumps([article_summary(a) for a in articles], indent=2))


def cmd_articles_by_user(args):
    # Public read: no credential loaded.
    result = call("GET", "/articles",
                  params={"username": args.username, "page": args.page,
                          "per_page": args.per_page},
                  authed=False)
    articles = result if isinstance(result, list) else []
    print(json.dumps([article_summary(a) for a in articles], indent=2))


def parse_tags(tags: str | None) -> list[str]:
    if not tags:
        return []
    out = [t.strip() for t in tags.split(",") if t.strip()]
    if len(out) > 4:
        sys.exit(f"error: dev.to allows max 4 tags; got {len(out)}")
    return out


def body_text(args) -> str:
    if args.body_file:
        if not os.path.isfile(args.body_file):
            sys.exit(f"error: no file at {args.body_file}")
        with open(args.body_file, "r", encoding="utf-8") as fh:
            return fh.read()
    return args.body_markdown


def cmd_article_create(args):
    text = body_text(args)
    if not text:
        sys.exit("error: provide --body-markdown or --body-file")
    article = {
        "title": args.title,
        "body_markdown": text,
        "published": args.published,
        "tags": parse_tags(args.tags),
    }
    if args.series:
        article["series"] = args.series
    if args.canonical_url:
        article["canonical_url"] = args.canonical_url
    result = call("POST", "/articles", payload={"article": article})
    if not isinstance(result, dict):
        sys.exit("error: unexpected response from dev.to")
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "url": result.get("url"),
                      "published": result.get("published")}, indent=2))


def cmd_article_update(args):
    article = {}
    if args.title is not None:
        article["title"] = args.title
    if args.body_markdown is not None or args.body_file is not None:
        article["body_markdown"] = body_text(args)
    if args.tags is not None:
        article["tags"] = parse_tags(args.tags)
    if args.publish:
        article["published"] = True
    if args.unpublish:
        article["published"] = False
    if not article:
        sys.exit("error: nothing to update; pass a field to change")
    result = call("PUT", f"/articles/{args.id}", payload={"article": article})
    if not isinstance(result, dict):
        sys.exit("error: unexpected response from dev.to")
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "url": result.get("url"),
                      "published": result.get("published")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="dev.to API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("me", help="verify the API key (own profile)")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("my-articles", help="list own articles")
    p.add_argument("--state", default="published",
                   choices=["published", "unpublished", "all"])
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--per-page", type=int, default=30)
    p.set_defaults(func=cmd_my_articles)

    p = sub.add_parser("articles-by-user", help="public articles by username (no key needed)")
    p.add_argument("--username", required=True)
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--per-page", type=int, default=30)
    p.set_defaults(func=cmd_articles_by_user)

    p = sub.add_parser("article-create",
                       help="create an article; draft unless --published (confirm first for publishes)")
    p.add_argument("--title", required=True)
    p.add_argument("--body-markdown", default=None)
    p.add_argument("--body-file", default=None, help="markdown file to upload as the body")
    p.add_argument("--tags", default=None, help="comma-separated, max 4")
    p.add_argument("--published", action="store_true",
                   help="go live immediately (default is draft)")
    p.add_argument("--series", default=None)
    p.add_argument("--canonical-url", default=None)
    p.set_defaults(func=cmd_article_create)

    p = sub.add_parser("article-update", help="update an article (confirm first)")
    p.add_argument("--id", required=True, help="article id")
    p.add_argument("--title", default=None)
    p.add_argument("--body-markdown", default=None)
    p.add_argument("--body-file", default=None)
    p.add_argument("--tags", default=None, help="comma-separated, max 4")
    p.add_argument("--publish", action="store_true", help="publish the article")
    p.add_argument("--unpublish", action="store_true", help="unpublish back to draft")
    p.set_defaults(func=cmd_article_update)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
