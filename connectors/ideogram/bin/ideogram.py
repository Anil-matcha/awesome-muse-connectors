#!/usr/bin/env python3
"""Minimal Ideogram API CLI for the muse-connectors ideogram skill.

Auth: loads the per-user `custom.ideogram` credential (dashboard API key)
as a surrogate via the bundled dynamic_credentials helper. The real key
never touches this script: the runtime swaps the surrogate on approved
egress, only to api.ideogram.ai.

HEADER NOTE: the research dossier documents "header auth" for Ideogram
without naming the header. This CLI sends `Api-Key: <key>`, which is the
documented scheme in Ideogram's published API docs; VERIFY against
developer.ideogram.ai before first live use and fix here if it differs.

Ideogram responses are SYNCHRONOUS (no job polling), but image URLs
expire: download immediately after generation.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.ideogram"
ALLOWED_HOSTS = ("api.ideogram.ai",)
BASE = "https://api.ideogram.ai"

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


def multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = bytearray()
    for key, value in fields.items():
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        body += f"{value}\r\n".encode()
    for key, path in files.items():
        name = path.rsplit("/", 1)[-1]
        with open(path, "rb") as fh:
            blob = fh.read()
        body += f"--{boundary}\r\n".encode()
        body += (f'Content-Disposition: form-data; name="{key}"; '
                 f'filename="{name}"\r\n').encode()
        body += "Content-Type: application/octet-stream\r\n\r\n".encode()
        body += blob + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def call(method: str, path: str, fields: dict | None = None,
         files: dict | None = None, payload: dict | None = None) -> dict:
    url = BASE + path
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    data = None
    headers = {}
    if fields is not None or files is not None:
        data, ctype = multipart(fields or {}, files or {})
        headers["Content-Type"] = ctype
    elif payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    req.add_header("Api-Key", api_key())  # see HEADER NOTE above
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", body.get("message", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: Ideogram returned HTTP {exc.code}: {msg}")
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


def _print_urls(result: dict) -> None:
    images = result.get("images", []) if isinstance(result, dict) else []
    urls = [img.get("url") for img in images if isinstance(img, dict) and img.get("url")]
    print(json.dumps({"ok": True, "image_urls": urls}, indent=2))
    if urls:
        print("note: image URLs expire; download immediately and do not store the URL as the artifact.",
              file=sys.stderr)


def cmd_auth(_args):
    # Billing/balance read is free and exercises the key + header.
    result = cmd_balance_raw()
    print(json.dumps({"ok": True, "billing": result}, indent=2))


def cmd_balance_raw() -> dict:
    # Path per Ideogram's public docs ("read balance first"); not in the
    # research dossier, so verify against developer.ideogram.ai if it 404s.
    return call("GET", "/api/v1/billing")


def cmd_balance(_args):
    print(json.dumps(cmd_balance_raw(), indent=2))


def cmd_generate(args):
    fields = {"prompt": args.prompt}
    fields.update({k: str(v) for k, v in _parse_json_arg(args.json).items()})
    result = call("POST", "/v1/ideogram-v3/generate", fields=fields)
    _print_urls(result)


def cmd_edit(args):
    fields = {"prompt": args.prompt}
    fields.update({k: str(v) for k, v in _parse_json_arg(args.json).items()})
    result = call("POST", "/v1/ideogram-v3/edit", fields=fields,
                  files={"image": args.image})
    _print_urls(result)


def cmd_remix(args):
    fields = {"prompt": args.prompt}
    fields.update({k: str(v) for k, v in _parse_json_arg(args.json).items()})
    result = call("POST", "/v1/ideogram-v3/remix", fields=fields,
                  files={"image": args.image})
    _print_urls(result)


def cmd_upscale(args):
    fields = _parse_json_arg(args.json)
    fields = {k: str(v) for k, v in fields.items()}
    result = call("POST", "/upscale", fields=fields, files={"image": args.image})
    _print_urls(result)


def cmd_describe(args):
    result = call("POST", "/describe", fields={}, files={"image": args.image})
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Ideogram API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key (free balance read)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("balance", help="read billing balance (free)")
    p.set_defaults(func=cmd_balance)

    p = sub.add_parser("generate", help="text-to-image (confirm first; billed)")
    p.add_argument("--prompt", required=True)
    p.add_argument("--json", default=None,
                   help="extra fields (aspect_ratio, style, etc.) as a JSON object")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("edit", help="Magic Fill edit of an image (confirm first; billed)")
    p.add_argument("--prompt", required=True)
    p.add_argument("--image", required=True, help="input image path")
    p.add_argument("--json", default=None)
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("remix", help="style-transfer remix of an image (confirm first; billed)")
    p.add_argument("--prompt", required=True)
    p.add_argument("--image", required=True, help="input image path")
    p.add_argument("--json", default=None)
    p.set_defaults(func=cmd_remix)

    p = sub.add_parser("upscale", help="upscale an image (confirm first; billed)")
    p.add_argument("--image", required=True, help="input image path")
    p.add_argument("--json", default=None)
    p.set_defaults(func=cmd_upscale)

    p = sub.add_parser("describe", help="describe an image")
    p.add_argument("--image", required=True, help="input image path")
    p.set_defaults(func=cmd_describe)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
