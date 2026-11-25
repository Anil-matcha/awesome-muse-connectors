#!/usr/bin/env python3
"""Minimal PostHog API CLI for the muse-connectors posthog skill.

Auth: loads the per-user `custom.posthog` credential as a surrogate via the
bundled dynamic_credentials helper. The real key never touches this script:
the runtime swaps the surrogate on approved egress, only to the configured
PostHog host (default app.posthog.com).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.posthog"
DEFAULT_HOST = "app.posthog.com"

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


def norm_host(raw: str) -> str:
    host = raw.strip()
    for scheme in ("https://", "http://"):
        if host.startswith(scheme):
            host = host[len(scheme):]
    return host.rstrip("/")


def call(args, path: str, params: dict | None = None) -> dict:
    host = norm_host(args.host)
    url = f"https://{host}/api" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=(host,))
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        sys.exit(f"error: posthog API returned HTTP {exc.code}: {body}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_me(args):
    user = call(args, "/users/@me/")
    print(json.dumps(
        {"id": user.get("id"), "email": user.get("email"),
         "first_name": user.get("first_name")},
        indent=2,
    ))


def cmd_projects(args):
    result = call(args, "/projects/")
    out = [{"id": t.get("id"), "name": t.get("name")}
           for t in result.get("results", [])]
    print(json.dumps(out, indent=2))


def cmd_insights(args):
    result = call(args, f"/projects/{args.project}/insights/",
                  params={"limit": args.limit})
    out = [{"id": i.get("id"), "name": i.get("name"),
            "derived_name": i.get("derived_name")}
           for i in result.get("results", [])]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="PostHog API CLI (muse-connectors)")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="PostHog app host, e.g. app.posthog.com or eu.posthog.com "
                             "(not the us.i.posthog.com ingestion host)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("me", help="verify the connection")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("projects", help="list projects")
    p.set_defaults(func=cmd_projects)

    p = sub.add_parser("insights", help="saved insights in a project")
    p.add_argument("--project", required=True, help="numeric project ID")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_insights)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
