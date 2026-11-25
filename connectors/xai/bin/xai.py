#!/usr/bin/env python3
"""xAI (Grok) API CLI for the muse-connectors xai skill.

Auth: loads the per-user `custom.xai` credential as a surrogate via the
bundled dynamic_credentials helper. xAI uses an API key sent as
Authorization: Bearer. The real key never touches this script: the runtime
swaps the surrogate on approved egress, only to api.x.ai.

Endpoints: OpenAI-compatible, base https://api.x.ai/v1.
GET /v1/models lists models; POST /v1/chat/completions runs completions.

Safety: chat completions spend real money per token (see the models and
pricing page at https://docs.x.ai/developers/models). The CLI prints usage
(prompt/completion/total tokens) with every completion so the cost is
visible. No confirmation gate is needed: this is ordinary API usage, but
never run large or repeated generations without the user asking.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.xai"
ALLOWED_HOSTS = ("api.x.ai",)
BASE = "https://api.x.ai/v1"
DEFAULT_MODEL = "grok-4.6"
CONNECT_GUIDANCE = (
    "not connected: create an xAI API key (xAI console > API keys) and "
    "collect it via the secure credential flow "
    "(credentials.request_api_access) as `custom.xai`, then retry."
)

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


def call(method: str, path: str, payload: dict | None = None) -> dict:
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        if "missing" in str(exc) or "surrogate" in str(exc):
            sys.exit(CONNECT_GUIDANCE)
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            msg = body[:500]
        except Exception:
            msg = str(exc)
        sys.exit(f"error: xai returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(args):
    call("GET", "/models")
    print(json.dumps({"ok": True,
                      "note": "credential accepted"}, indent=2))


def cmd_models(args):
    result = call("GET", "/models")
    items = result.get("data", []) if isinstance(result, dict) else result
    out = [{"id": m.get("id"), "created": m.get("created"),
            "owned_by": m.get("owned_by")}
           for m in items]
    print(json.dumps(out, indent=2))


def cmd_chat(args):
    prompt = args.message if args.message is not None else args.prompt
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": args.model, "messages": messages}
    if args.temperature is not None:
        payload["temperature"] = args.temperature
    if args.max_tokens is not None:
        payload["max_tokens"] = args.max_tokens
    result = call("POST", "/chat/completions", payload)
    choices = result.get("choices", [])
    text = ""
    if choices:
        message = choices[0].get("message", {})
        text = message.get("content") or ""
    usage = result.get("usage", {})
    print(json.dumps({
        "model": result.get("model", args.model),
        "content": text,
        "finish_reason": choices[0].get("finish_reason") if choices else None,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "note": "completions are billed per token; see "
                "https://docs.x.ai/developers/models for pricing",
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="xAI (Grok) API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("models", help="list available Grok models")
    p.set_defaults(func=cmd_models)

    p = sub.add_parser("chat", help="send a chat completion (spends tokens)")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"model id (default: {DEFAULT_MODEL}); "
                        "use `models` to see the live list")
    p.add_argument("--message", default=None,
                   help="the user message to send")
    p.add_argument("--prompt", default=None,
                   help="alias of --message")
    p.add_argument("--system", default=None,
                   help="optional system prompt")
    p.add_argument("--temperature", type=float, default=None,
                   help="sampling temperature, e.g. 0.7")
    p.add_argument("--max-tokens", type=int, default=None,
                   help="cap on completion tokens")
    p.set_defaults(func=cmd_chat)

    args = parser.parse_args()
    if args.command == "chat" and args.message is None and args.prompt is None:
        parser.error("chat needs --message (or --prompt)")
    args.func(args)


if __name__ == "__main__":
    main()
