#!/usr/bin/env python3
"""Call the OpenRouter API (OpenAI-compatible) with the stored custom.openrouter credential.

Never prints or persists the raw key; auth goes through the authd surrogate
exchange via dynamic_credentials.add_surrogate_to_request.
"""
import argparse
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import (
    add_surrogate_to_request,
    read_json_response,
    DynamicCredentialError,
)

BASE = "https://openrouter.ai/api/v1"
ALLOWED = ["openrouter.ai"]
CRED = "custom.openrouter"


def _request(method, path, body=None, auth=True):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", "muse-agent/1.0")
    req.add_header("HTTP-Referer", "https://muse.ai")
    req.add_header("X-Title", "Muse")
    if data:
        req.add_header("Content-Type", "application/json")
    if auth:
        add_surrogate_to_request(
            req, CRED, entry_name="access_token", allowed_hosts=ALLOWED
        )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = {"error": f"HTTP {e.code}"}
        return e.code, payload


def cmd_models(args):
    # /models is a public endpoint: call it unauthenticated (ported from the
    # awesome-muse-connectors catalog version 2026-10-19, minus its credential
    # attachment on this public call).
    status, payload = _request("GET", "/models", auth=False)
    models = [m for m in payload.get("data", []) if isinstance(m, dict)]
    if args.free_only:
        models = [m for m in models if ":free" in m.get("id", "")]
    if args.filter:
        needle = args.filter.lower()
        models = [
            m
            for m in models
            if needle in m.get("id", "").lower()
            or needle in m.get("name", "").lower()
        ]
    total = len(models)
    models = models[: args.limit] if args.limit else models
    out = [
        {
            "id": m.get("id"),
            "name": m.get("name"),
            "prompt_price": (m.get("pricing") or {}).get("prompt"),
            "completion_price": (m.get("pricing") or {}).get("completion"),
            "context_length": m.get("context_length"),
        }
        for m in models
    ]
    print(
        json.dumps(
            {"status": status, "count": total, "shown": len(out), "models": out},
            indent=2,
        )[:8000]
    )


def cmd_key(args):
    status, payload = _request("GET", "/auth/key")
    key = payload.get("data", {}) if isinstance(payload, dict) else {}
    print(
        json.dumps(
            {
                "status": status,
                "label": key.get("label"),
                "usage": key.get("usage"),
                "limit": key.get("limit"),
                "limit_remaining": key.get("limit_remaining"),
                "is_free_tier": key.get("is_free_tier"),
            },
            indent=2,
        )
    )


def cmd_chat(args):
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})
    body = {
        "model": args.model,
        "messages": messages,
        "max_tokens": args.max_tokens,
    }
    if args.temperature is not None:
        body["temperature"] = args.temperature
    status, payload = _request("POST", "/chat/completions", body)
    if status == 200:
        choices = payload.get("choices", [])
        text = choices[0]["message"]["content"] if choices else None
        print(json.dumps({"status": status, "text": text}, indent=2)[:8000])
    else:
        print(json.dumps({"status": status, "payload": payload}, indent=2)[:4000])


def main():
    p = argparse.ArgumentParser(description="OpenRouter API CLI (vault credential)")
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("models", help="list available models")
    m.add_argument("--free-only", action="store_true",
                   help="show only :free models")
    m.add_argument("--filter", default="",
                   help="substring filter on model id or name")
    m.add_argument("--limit", type=int, default=50,
                   help="max models to show (0 = all)")
    sub.add_parser("key", help="show the connected key's label, usage, limit")
    c = sub.add_parser("chat", help="chat completion")
    c.add_argument("--model", default="meta-llama/llama-3.3-70b-instruct")
    c.add_argument("--prompt", required=True)
    c.add_argument("--system", default=None)
    c.add_argument("--max-tokens", type=int, default=1024)
    c.add_argument("--temperature", type=float, default=None)
    args = p.parse_args()
    try:
        if args.cmd == "models":
            cmd_models(args)
        elif args.cmd == "key":
            cmd_key(args)
        else:
            cmd_chat(args)
    except DynamicCredentialError as e:
        print(json.dumps({"error": f"credential: {e}"}))
        sys.exit(2)


if __name__ == "__main__":
    main()
