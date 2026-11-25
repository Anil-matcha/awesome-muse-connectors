#!/usr/bin/env python3
"""Minimal Anthropic API CLI for the muse-connectors Anthropic skill.

Auth: loads the per-user `custom.anthropic` credential as a surrogate via the
bundled dynamic_credentials helper. The real key never touches this script:
the runtime swaps the surrogate on approved egress, only to api.anthropic.com.

Every request also carries the required `anthropic-version: 2023-06-01`
header. Read-only by design: the only call is GET /v1/models.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.anthropic"
ALLOWED_HOSTS = ("api.anthropic.com",)
API = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"

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


def call(path: str) -> dict:
    url = API + path
    req = urllib.request.Request(url, headers={"anthropic-version": ANTHROPIC_VERSION})
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
            detail = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            detail = str(exc)
        sys.exit(f"error: anthropic returned HTTP {exc.code}: {detail}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    return result


def cmd_models(args):
    result = call("/v1/models")
    models = [
        {"id": m.get("id"), "display_name": m.get("display_name")}
        for m in result.get("data", [])
    ]
    print(json.dumps(models, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Anthropic API CLI (muse-connectors, read-only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("models", help="list models available to this key")
    p.set_defaults(func=cmd_models)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
