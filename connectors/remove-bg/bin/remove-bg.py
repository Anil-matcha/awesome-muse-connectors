#!/usr/bin/env python3
"""Minimal remove.bg CLI for the muse-connectors remove-bg skill, served by Leonardo.Ai.

remove.bg's API moved to Leonardo.Ai on December 1, 2026. Background removal now
runs through Leonardo's sync API with the `remove-bg` model, following the official
migration guide:
https://docs.leonardo.ai/docs/migrate-from-the-removebg-api-to-leonardoai

Auth: a Leonardo.Ai API key loaded as a surrogate for `custom.remove-bg` via the
bundled dynamic_credentials helper, sent as `Authorization: Bearer YOUR_API_KEY`
(placement resolved by the helper from the credential config). The real key never
touches this script: the runtime swaps the surrogate on approved egress, only to
cloud.leonardo.ai. remove.bg keys do not work on Leonardo.

`process` asks for the result inline (`base64: true`, `ephemeral: true`), decodes
`results[0].dataB64`, saves it to the --out path and prints the path along with the
call's `cost`. Every call is billed, so confirm before processing.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.remove-bg"
ALLOWED_HOSTS = ("cloud.leonardo.ai",)
API = "https://cloud.leonardo.ai/api/rest/v2"
SIZES = ("preview", "full", "auto", "50MP")
TYPES = ("auto", "person", "product", "car", "animal", "graphic", "transportation", "other")

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


def credential_error(exc: Exception) -> None:
    sys.exit(
        "error: no stored credential for custom.remove-bg "
        f"({exc}). To connect, ask Muse to connect a Leonardo.Ai API key (remove.bg's "
        "API moved to Leonardo.Ai) via the secure credential flow, then retry."
    )


def error_message(body) -> str:
    """Leonardo reports errors as `errors[0].message`, often with HTTP 200."""
    if isinstance(body, dict):
        errors = body.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            return str(errors[0].get("message") or errors[0])
        if body.get("error"):
            return str(body["error"])
    return ""


def api_error(exc: urllib.error.HTTPError) -> None:
    try:
        msg = error_message(json.loads(exc.read().decode("utf-8", errors="replace"))) or str(exc)
    except Exception:
        msg = str(exc)
    hint = ""
    if exc.code in (401, 403):
        hint = " (remove.bg keys don't work here: reconnect custom.remove-bg with a Leonardo.Ai API key)"
    sys.exit(f"error: Leonardo.Ai returned HTTP {exc.code}: {msg}{hint}")


def authed_request(url: str, payload: dict | None = None):
    headers: dict[str, str] = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except (DynamicCredentialError, OSError) as exc:
        credential_error(exc)
    return req


def call(req, timeout: int):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        api_error(exc)
    except Exception as exc:
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    # Read-only and free: listing the available models only needs a valid key.
    result = call(authed_request(API + "/models"), timeout=30)
    if error_message(result):
        sys.exit(f"error: Leonardo.Ai: {error_message(result)}")
    print(json.dumps({"ok": True}, indent=2))


def cmd_process(args):
    if args.file:
        try:
            with open(args.file, "rb") as fh:
                image = {"type": "BASE64", "data": base64.b64encode(fh.read()).decode("ascii")}
        except OSError as exc:
            sys.exit(f"error: cannot read file: {exc}")
    else:
        image = {"type": "URL", "url": args.url}
    payload = {
        "model": "remove-bg",
        "ephemeral": True,
        "base64": True,
        "parameters": {
            "size": args.size,
            "type": args.type,
            "format": "png",
            "guidances": {"image_reference": [{"image": image}]},
        },
    }
    result = call(authed_request(API + "/generationssync", payload), timeout=120)
    results = result.get("results") if isinstance(result, dict) else None
    if not results or not results[0].get("dataB64"):
        sys.exit(f"error: Leonardo.Ai: {error_message(result) or 'no image returned (blocked by moderation?)'}")
    image_bytes = base64.b64decode(results[0]["dataB64"])
    try:
        with open(args.out, "wb") as fh:
            fh.write(image_bytes)
    except OSError as exc:
        sys.exit(f"error: cannot write file: {exc}")
    print(json.dumps({"saved_to": args.out, "bytes": len(image_bytes), "cost": result.get("cost")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="remove.bg CLI on Leonardo.Ai (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("process", help="remove the background from an image")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="local image file path (up to ~7.5MB)")
    group.add_argument("--url", help="HTTPS image URL to process")
    p.add_argument("--out", required=True, help="local path to save the result PNG")
    p.add_argument("--size", default="auto", choices=SIZES, help="output resolution (default: auto)")
    p.add_argument("--type", default="auto", choices=TYPES, help="foreground type (default: auto)")
    p.set_defaults(func=cmd_process)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
