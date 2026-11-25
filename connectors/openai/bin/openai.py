#!/usr/bin/env python3
"""Minimal OpenAI API CLI for the muse-connectors OpenAI skill.

Auth: loads the per-user `custom.openai` credential as a surrogate via the
bundled dynamic_credentials helper. The real key never touches this script:
the runtime swaps the surrogate on approved egress, only to api.openai.com.

Read-only by design: the only call is GET /v1/models.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.openai"
ALLOWED_HOSTS = ("api.openai.com",)
API = "https://api.openai.com/v1"

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
    req = urllib.request.Request(url)
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
        sys.exit(f"error: openai returned HTTP {exc.code}: {detail}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    return result


def cmd_models(args):
    result = call("/models")
    models = [
        {"id": m.get("id"), "owned_by": m.get("owned_by")}
        for m in result.get("data", [])
    ][:40]
    print(json.dumps(models, indent=2))


def main():
    parser = argparse.ArgumentParser(description="OpenAI API CLI (muse-connectors, read-only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("models", help="list models available to this key")
    p.set_defaults(func=cmd_models)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
