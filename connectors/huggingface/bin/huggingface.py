#!/usr/bin/env python3
"""Minimal Hugging Face Hub API CLI for the muse-connectors Hugging Face skill.

Auth: loads the per-user `custom.huggingface` credential as a surrogate via
the bundled dynamic_credentials helper. The real token never touches this
script: the runtime swaps the surrogate on approved egress, only to
huggingface.co. Read-only: no repo writes ship.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.huggingface"
ALLOWED_HOSTS = ("huggingface.co",)
API = "https://huggingface.co/api"

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


def call(path: str, params: dict | None = None) -> dict | list:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
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
            detail = json.loads(body).get("error", body)
        except Exception:
            detail = str(exc)
        sys.exit(f"error: huggingface returned HTTP {exc.code}: {detail}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    return result


def cmd_me(_args):
    result = call("/whoami-v2")
    print(json.dumps(
        {"name": result.get("name"), "email": result.get("email"),
         "type": result.get("type")},
        indent=2))


def cmd_models(args):
    results = call("/models", params={"search": args.query, "limit": 10})
    models = [
        {"id": m.get("id"), "likes": m.get("likes"),
         "downloads": m.get("downloads")}
        for m in results
    ]
    print(json.dumps(models, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Hugging Face Hub API CLI (muse-connectors, read-only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("me", help="verify account (whoami)")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("models", help="search the model hub")
    p.add_argument("--query", required=True, help="search term, e.g. llama")
    p.set_defaults(func=cmd_models)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
