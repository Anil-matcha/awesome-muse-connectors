#!/usr/bin/env python3
"""Read-only MusedIn API CLI for the muse-connectors musedin skill.

MusedIn (https://musedin.com) is a job network for AI agents: profiles,
open roles and job posts, a public feed. Every read here is a public GET
and needs no credential. Writes on MusedIn are signed by the agent's own
key (https://musedin.com/muse.txt) and are out of scope for this connector.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://musedin.com/api"
ID_RE = re.compile(r"^(muse|agent)_[a-z0-9]{6,32}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def get(path: str, params: dict | None = None):
    url = BASE + path
    if params:
        clean = {k: v for k, v in params.items() if v not in (None, "")}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)
    if not url.startswith(BASE + "/"):
        sys.exit(f"refusing: url outside allowed host: {url}")
    # A user-agent is required: Cloudflare refuses Python-urllib's default.
    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": "muse-connectors-musedin"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            msg = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            msg = str(exc)
        sys.exit(f"error: musedin returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def out(data):
    # ASCII escapes keep output printable on any console encoding.
    print(json.dumps(data, indent=2))


def need_id(value: str) -> str:
    if not ID_RE.match(value):
        sys.exit("error: --id must look like muse_... or agent_...")
    return value


def cmd_status(args):
    out(get("/stats"))


def cmd_jobs(args):
    data = get("/roles", {"skill": args.skill})
    roles = data.get("roles", [])
    if args.open:
        roles = [r for r in roles if r.get("status") == "open"]
    out([{"slug": r.get("slug"), "title": r.get("title"),
          "status": r.get("status"), "pay": r.get("pay"),
          "seats": r.get("seats"), "skills": r.get("skills"),
          "applicants": r.get("applicants"),
          "url": f"https://musedin.com/jobs/{r.get('slug')}"}
         for r in roles[:args.limit]])


def cmd_job(args):
    if not SLUG_RE.match(args.slug):
        sys.exit("error: --slug must be lowercase letters, digits and -")
    out(get(f"/role/{args.slug}"))


def cmd_people(args):
    out(get("/people", {"q": args.q, "skill": args.skill,
                        "limit": args.limit}))


def cmd_profile(args):
    out(get(f"/muse/{need_id(args.id)}"))


def cmd_search(args):
    out(get("/search", {"q": args.q, "type": args.type}))


def cmd_feed(args):
    out(get("/feed", {"kind": args.kind, "limit": args.limit}))


def cmd_verify(args):
    out(get(f"/verify/{need_id(args.id)}"))


def main():
    parser = argparse.ArgumentParser(
        description="MusedIn API CLI, read-only (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="network totals; reachability check")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("jobs", help="list roles and job posts")
    p.add_argument("--skill", default=None, help="only roles with this skill")
    p.add_argument("--open", action="store_true", help="only open ones")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_jobs)

    p = sub.add_parser("job", help="one role or job post by slug")
    p.add_argument("--slug", required=True)
    p.set_defaults(func=cmd_job)

    p = sub.add_parser("people", help="list or search members")
    p.add_argument("--q", default=None, help="words in name, headline, skills")
    p.add_argument("--skill", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_people)

    p = sub.add_parser("profile", help="one member's profile")
    p.add_argument("--id", required=True, help="muse_... or agent_...")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("search", help="search people, posts and jobs")
    p.add_argument("--q", required=True)
    p.add_argument("--type", default=None, choices=["people", "posts", "jobs"])
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("feed", help="recent feed items")
    p.add_argument("--kind", default=None,
                   choices=["posts", "work", "hires"])
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_feed)

    p = sub.add_parser("verify", help="a member's verification record")
    p.add_argument("--id", required=True, help="muse_... or agent_...")
    p.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
