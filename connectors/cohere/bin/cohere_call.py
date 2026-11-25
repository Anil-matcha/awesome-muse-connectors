#!/usr/bin/env python3
"""Call the Cohere API (chat, embed, rerank) with the stored custom.cohere credential.

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

BASE = "https://api.cohere.com"
ALLOWED = ["api.cohere.com"]
CRED = "custom.cohere"


def _request(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
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
    status, payload = _request("GET", "/v2/models")
    count = len([m for m in payload.get("models", []) if isinstance(m, dict)])
    print(json.dumps({"ok": status == 200, "status": status, "models": count}))
    if status != 200:
        sys.exit(1)


def cmd_models(_args):
    status, payload = _request("GET", "/v2/models")
    names = [
        m.get("name")
        for m in payload.get("models", [])
        if isinstance(m, dict) and "name" in m
    ]
    print(json.dumps({"status": status, "models": names}, indent=2)[:4000])


def cmd_chat(args):
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})
    body = {"model": args.model, "messages": messages}
    status, payload = _request("POST", "/v2/chat", body)
    if status == 200:
        msg = payload.get("message", {})
        content = msg.get("content", [])
        text = "".join(
            c.get("text", "")
            for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        )
        print(json.dumps({"status": status, "text": text}, indent=2)[:8000])
    else:
        print(json.dumps({"status": status, "payload": payload}, indent=2)[:4000])


def cmd_embed(args):
    body = {
        "model": args.model,
        "texts": args.text,
        "input_type": args.input_type,
        "embedding_types": ["float"],
    }
    status, payload = _request("POST", "/v2/embed", body)
    if status == 200:
        vectors = (payload.get("embeddings") or {}).get("float") or []
        out = {"status": status, "count": len(vectors),
               "dimensions": len(vectors[0]) if vectors else 0}
        if args.show_first and vectors:
            out["first"] = vectors[0][:8]
        print(json.dumps(out, indent=2))
    else:
        print(json.dumps({"status": status, "payload": payload}, indent=2)[:4000])


def cmd_rerank(args):
    body = {"model": args.model, "query": args.query,
            "documents": args.doc, "top_n": args.top_n}
    status, payload = _request("POST", "/v2/rerank", body)
    if status == 200:
        results = [
            {"index": r.get("index"), "score": r.get("relevance_score")}
            for r in payload.get("results", [])
        ]
        print(json.dumps({"status": status, "results": results}, indent=2))
    else:
        print(json.dumps({"status": status, "payload": payload}, indent=2)[:4000])


def main():
    p = argparse.ArgumentParser(description="Cohere API CLI (vault credential)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth", help="verify the stored credential answers")
    sub.add_parser("models", help="list available models")
    c = sub.add_parser("chat", help="chat completion")
    c.add_argument("--model", default="command-a-03-2025")
    c.add_argument("--prompt", required=True)
    c.add_argument("--system", default=None)
    e = sub.add_parser("embed", help="embed texts")
    e.add_argument("--model", default="embed-v4.0")
    e.add_argument("--text", action="append", required=True,
                   help="text to embed (repeatable)")
    e.add_argument("--input-type", default="search_document",
                   choices=["search_document", "search_query",
                            "classification", "clustering"])
    e.add_argument("--show-first", action="store_true",
                   help="print the first 8 dimensions of the first vector")
    r = sub.add_parser("rerank", help="rerank documents against a query")
    r.add_argument("--model", default="rerank-v3.5")
    r.add_argument("--query", required=True)
    r.add_argument("--doc", action="append", required=True,
                   help="candidate document (repeatable)")
    r.add_argument("--top-n", type=int, default=3)
    args = p.parse_args()
    try:
        if args.cmd == "auth":
            cmd_auth(args)
        elif args.cmd == "models":
            cmd_models(args)
        elif args.cmd == "embed":
            cmd_embed(args)
        elif args.cmd == "rerank":
            cmd_rerank(args)
        else:
            cmd_chat(args)
    except DynamicCredentialError as e:
        print(json.dumps({"error": f"credential: {e}"}))
        sys.exit(2)


if __name__ == "__main__":
    main()
