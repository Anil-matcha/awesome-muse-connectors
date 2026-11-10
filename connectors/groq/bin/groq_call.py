#!/usr/bin/env python3
"""Call the Groq API (OpenAI-compatible) with the stored custom.groq credential.

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

BASE = "https://api.groq.com/openai/v1"
ALLOWED = ["api.groq.com"]
CRED = "custom.groq"


def _request(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    # Groq sits behind Cloudflare, which blocks urllib's default User-Agent
    # (error 1010). A browser UA passes.
    req.add_header(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    if data:
        req.add_header("Content-Type", "application/json")
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


def cmd_auth(_args):
    status, payload = _request("GET", "/models")
    count = len([m for m in payload.get("data", []) if isinstance(m, dict)])
    print(json.dumps({"ok": status == 200, "status": status, "models": count}))
    if status != 200:
        sys.exit(1)


def cmd_models(_args):
    status, payload = _request("GET", "/models")
    models = [
        m.get("id")
        for m in payload.get("data", [])
        if isinstance(m, dict) and "id" in m
    ]
    print(json.dumps({"status": status, "models": models}, indent=2)[:4000])


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
    p = argparse.ArgumentParser(description="Groq API CLI (vault credential)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth", help="verify the stored credential answers")
    sub.add_parser("models", help="list available models")
    c = sub.add_parser("chat", help="chat completion")
    c.add_argument("--model", default="openai/gpt-oss-20b")
    c.add_argument("--prompt", required=True)
    c.add_argument("--system", default=None)
    c.add_argument("--max-tokens", type=int, default=1024)
    c.add_argument("--temperature", type=float, default=None)
    args = p.parse_args()
    try:
        if args.cmd == "auth":
            cmd_auth(args)
        elif args.cmd == "models":
            cmd_models(args)
        else:
            cmd_chat(args)
    except DynamicCredentialError as e:
        print(json.dumps({"error": f"credential: {e}"}))
        sys.exit(2)


if __name__ == "__main__":
    main()
