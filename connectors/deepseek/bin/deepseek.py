#!/usr/bin/env python3
"""DeepSeek API CLI for the muse-connectors deepseek skill.

Auth: loads the per-user `custom.deepseek` credential as a surrogate via
the bundled dynamic_credentials helper. DeepSeek uses an API key sent as
Authorization: Bearer (OpenAI-compatible). The real key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.deepseek.com.

Cost: every `chat` call consumes paid DeepSeek API tokens; usage is
reported on every response. `models` and `balance` are read-only and
spend nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.deepseek"
ALLOWED_HOSTS = ("api.deepseek.com",)
BASE = "https://api.deepseek.com"
CONNECT_GUIDANCE = (
    "not connected: create a DeepSeek API key at "
    "https://platform.deepseek.com/api_keys and collect it via the secure "
    "credential flow (credentials.request_api_access) as `custom.deepseek`, "
    "then retry."
)
DEFAULT_MODEL = "deepseek-flash"

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
        sys.exit(f"error: deepseek returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(args):
    call("GET", "/models")
    print(json.dumps({"ok": True,
                      "note": "credential accepted"}, indent=2))


def cmd_models(args):
    result = call("GET", "/models")
    items = result.get("data", []) if isinstance(result, dict) else []
    out = [{"id": m.get("id"), "owned_by": m.get("owned_by")}
           for m in items]
    print(json.dumps(out, indent=2))


def cmd_chat(args):
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.message})
    payload: dict = {"model": args.model, "messages": messages,
                     "stream": False}
    if args.temperature is not None:
        payload["temperature"] = args.temperature
    if args.max_tokens is not None:
        payload["max_tokens"] = args.max_tokens
    if args.thinking is not None or args.reasoning_effort is not None:
        thinking: dict = {}
        if args.thinking is not None:
            thinking["type"] = args.thinking
        if args.reasoning_effort is not None:
            thinking["reasoning_effort"] = args.reasoning_effort
        payload["thinking"] = thinking
    result = call("POST", "/chat/completions", payload)
    choice = (result.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    usage = result.get("usage") or {}
    out = {
        "model": result.get("model"),
        "content": message.get("content"),
        "finish_reason": choice.get("finish_reason"),
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "cost_note": "this call consumed paid DeepSeek API tokens",
    }
    if message.get("reasoning_content"):
        out["reasoning_content"] = message.get("reasoning_content")
    print(json.dumps(out, indent=2))


def cmd_balance(args):
    result = call("GET", "/user/balance")
    print(json.dumps({
        "is_available": result.get("is_available"),
        "balance_infos": result.get("balance_infos", []),
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="DeepSeek API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("models", help="list available models (read-only)")
    p.set_defaults(func=cmd_models)

    p = sub.add_parser("chat", help="chat completion (spends paid tokens)")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="model id, e.g. deepseek-flash, deepseek-v4-pro "
                        f"(default: {DEFAULT_MODEL})")
    p.add_argument("--message", required=True,
                   help="the user message to send")
    p.add_argument("--system", default=None,
                   help="optional system prompt")
    p.add_argument("--temperature", type=float, default=None,
                   help="sampling temperature, 0-2")
    p.add_argument("--max-tokens", type=int, default=None,
                   help="max tokens in the response")
    p.add_argument("--thinking", choices=["enabled", "disabled"],
                   default=None,
                   help="thinking mode toggle (default: enabled per docs)")
    p.add_argument("--reasoning-effort",
                   choices=["none", "low", "high", "max"], default=None,
                   help="thinking effort; none disables thinking mode")
    p.set_defaults(func=cmd_chat)

    p = sub.add_parser("balance", help="account balance (read-only)")
    p.set_defaults(func=cmd_balance)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
