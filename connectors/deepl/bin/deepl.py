#!/usr/bin/env python3
"""Minimal DeepL API CLI for the muse-connectors DeepL skill.

Auth: loads the per-user `custom.deepl` credential as a surrogate via the
bundled dynamic_credentials helper. DeepL expects the non-standard header
`Authorization: DeepL-Auth-Key <key>`, so the CLI builds that header from the
surrogate itself (only the `hsurr:*` placeholder ever appears here; the runtime
swaps in the real key on approved egress, only to DeepL's API hosts).

Free-plan keys end in `:fx` and use api-free.deepl.com (the default); paid keys
use api.deepl.com — pass --host api.deepl.com for those.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.deepl"
ALLOWED_HOSTS = ("api-free.deepl.com", "api.deepl.com")
DEFAULT_HOST = "api-free.deepl.com"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        dynamic_credential_entry,
        ensure_allowed_url,
        read_json_response,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def auth_headers(url: str) -> dict:
    ensure_allowed_url(url, ALLOWED_HOSTS)
    try:
        entry = dynamic_credential_entry(CREDENTIAL_NAME)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    surrogate = str(entry["surrogate"]).strip()
    return {"Authorization": f"DeepL-Auth-Key {surrogate}"}


def call(host: str, method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    url = f"https://{host}" + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    headers.update(auth_headers(url))
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: deepl returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(args):
    result = call(args.host, "GET", "/v2/usage")
    counts = result.get("character_count", 0), result.get("character_limit", 0)
    print(json.dumps({"ok": True, "character_count": counts[0],
                      "character_limit": counts[1]}, indent=2))


def cmd_translate(args):
    payload = {"text": [args.text], "target_lang": args.target_lang}
    if args.source_lang:
        payload["source_lang"] = args.source_lang
    if args.formality:
        payload["formality"] = args.formality
    result = call(args.host, "POST", "/v2/translate", payload=payload)
    translations = result.get("translations", [])
    print(json.dumps(
        [{"text": t.get("text"), "detected_source": t.get("detected_source_language")}
         for t in translations], indent=2))


def cmd_languages(args):
    result = call(args.host, "GET", "/v2/languages",
                  params={"type": args.type})
    langs = [{"code": l.get("language"), "name": l.get("name")}
             for l in (result if isinstance(result, list) else [])]
    print(json.dumps(langs, indent=2))


def add_host_arg(p):
    p.add_argument("--host", default=DEFAULT_HOST,
                   choices=ALLOWED_HOSTS,
                   help="api-free.deepl.com for free keys (default), "
                        "api.deepl.com for paid keys")


def main():
    parser = argparse.ArgumentParser(description="DeepL API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the key and show usage")
    add_host_arg(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("translate", help="translate text")
    add_host_arg(p)
    p.add_argument("--text", required=True)
    p.add_argument("--target-lang", required=True,
                   help="e.g. FR, DE, ES, PT-BR, ZH")
    p.add_argument("--source-lang", default=None, help="e.g. EN")
    p.add_argument("--formality", default=None,
                   choices=["default", "more", "less", "prefer_more", "prefer_less"])
    p.set_defaults(func=cmd_translate)

    p = sub.add_parser("languages", help="list supported languages")
    add_host_arg(p)
    p.add_argument("--type", default="target", choices=["source", "target"])
    p.set_defaults(func=cmd_languages)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
