#!/usr/bin/env python3
"""Minimal Black Forest Labs (FLUX) API CLI for the muse-connectors black-forest-labs skill.

Auth: loads the per-user `custom.black-forest-labs` credential as a surrogate
via the bundled dynamic_credentials helper. The real API key never touches
this script: the runtime swaps the surrogate on approved egress, only to the
BFL hosts, and the CLI sends it verbatim as the `x-key` header.

Job flow: `generate` posts and prints a polling_url; poll it with `status`
until status is "Ready", then fetch the result. The result download URL
expires in 10 minutes: download immediately.

Regional hosts: api.bfl.ai (default), api.eu.bfl.ai (GDPR), api.us.bfl.ai.
FLUX has NO negative prompts: reframe as a positive description.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.black-forest-labs"
ALLOWED_HOSTS = ("api.bfl.ai", "api.eu.bfl.ai", "api.us.bfl.ai")
DEFAULT_HOST = "https://api.bfl.ai"

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


def api_key() -> str:
    try:
        return str(dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]).strip()
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")


def call(url: str, payload: dict | None = None) -> dict:
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    req.add_header("x-key", api_key())
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", body.get("message", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: BFL returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def poll(url: str) -> dict:
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    req = urllib.request.Request(url, method="GET")
    req.add_header("x-key", api_key())
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", body.get("message", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: BFL returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def _parse_json_arg(extra: str | None) -> dict:
    if not extra:
        return {}
    try:
        obj = json.loads(extra)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --json is not valid JSON: {exc}")
    if not isinstance(obj, dict):
        sys.exit("error: --json must be a JSON object")
    return obj


def host_of(args) -> str:
    return (args.region or DEFAULT_HOST).rstrip("/")


def cmd_auth(args):
    # BFL has no documented zero-cost probe; auth verifies the credential
    # is collected and well-formed. The first generate spends prepaid credit.
    key = api_key()
    if not key:
        sys.exit("error: empty credential")
    print(json.dumps({"ok": True, "host": host_of(args),
                      "note": "no zero-cost auth probe exists; auth checks "
                              "configuration only. First generate spends credit."},
                     indent=2))


def cmd_generate(args):
    payload = {"prompt": args.prompt}
    payload.update(_parse_json_arg(args.json))
    result = call(f"{host_of(args)}/v1/{args.model}", payload=payload)
    polling_url = result.get("polling_url")
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "polling_url": polling_url}, indent=2))
    print(f"poll with: bin/black-forest-labs.py status --polling-url '{polling_url}'",
          file=sys.stderr)


def cmd_status(args):
    result = poll(args.polling_url)
    status = result.get("status")
    out = {"status": status}
    if status == "Ready":
        sample = (result.get("result") or {}).get("sample")
        out["sample_url"] = sample
        print(json.dumps(out, indent=2))
        print("LOUD: the sample download URL expires in 10 minutes. "
              "Download immediately; do not store the URL as the artifact.",
              file=sys.stderr)
    else:
        out["detail"] = result
        print(json.dumps(out, indent=2))


def cmd_result(args):
    # Alias for status: BFL's polling URL already carries the result.
    cmd_status(args)


def main():
    parser = argparse.ArgumentParser(description="Black Forest Labs API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify credential configuration (no spend)")
    p.add_argument("--region", default=None,
                   help="regional host, e.g. https://api.eu.bfl.ai")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("generate", help="text-to-image with FLUX (confirm first; billed)")
    p.add_argument("--prompt", required=True,
                   help="positive description only; FLUX ignores negative prompts")
    p.add_argument("--model", default="flux-2-pro",
                   choices=["flux-2-pro", "flux-2-flex"],
                   help="flux-2-pro (general) or flux-2-flex (typography specialist)")
    p.add_argument("--region", default=None)
    p.add_argument("--json", default=None,
                   help="extra fields (width, height, seed, etc.) as a JSON object")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("status", help="poll a generation's polling_url")
    p.add_argument("--polling-url", required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("result", help="fetch a finished generation (alias of status)")
    p.add_argument("--polling-url", required=True)
    p.set_defaults(func=cmd_result)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
