#!/usr/bin/env python3
"""Minimal Perplexity API CLI for the muse-connectors perplexity skill.

Auth: loads the per-user `custom.perplexity` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.perplexity.ai.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.perplexity"
ALLOWED_HOSTS = ("api.perplexity.ai",)
API = "https://api.perplexity.ai"

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


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    url = API + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("error", str(exc)))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: Perplexity returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    result = call("GET", "/models")
    models = result.get("data", [])
    ids = [m.get("id") for m in models]
    print(json.dumps({"ok": True, "model_count": len(ids),
                      "models": ids[:20]}, indent=2))


def cmd_models(_args):
    result = call("GET", "/models")
    models = [
        {"id": m.get("id"), "created": m.get("created"),
         "owned_by": m.get("owned_by")}
        for m in result.get("data", [])
    ]
    print(json.dumps(models, indent=2))


def cmd_ask(args):
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.question}],
    }
    result = call("POST", "/chat/completions", payload=payload)
    choices = result.get("choices", [])
    message = choices[0].get("message", {}) if choices else {}
    print(json.dumps({"model": result.get("model"),
                      "answer": message.get("content"),
                      "citations": result.get("citations", [])}, indent=2))


def cmd_search(args):
    result = call("POST", "/search", payload={"query": args.query})
    hits = [
        {"title": h.get("title"), "url": h.get("url"),
         "snippet": h.get("snippet")}
        for h in result.get("results", [])
    ]
    print(json.dumps(hits, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Perplexity API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key (lists models)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("models", help="list available models")
    p.set_defaults(func=cmd_models)

    p = sub.add_parser("ask", help="ask a question with web search")
    p.add_argument("--model", required=True, help="model id, e.g. sonar")
    p.add_argument("--question", required=True, help="the question to ask")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("search", help="raw web search results")
    p.add_argument("--query", required=True, help="search query")
    p.set_defaults(func=cmd_search)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
