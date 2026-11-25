#!/usr/bin/env python3
"""Mistral AI (La Plateforme) API CLI for the muse-connectors mistral skill.

Auth: loads the per-user `custom.mistral` credential as a surrogate via the
bundled dynamic_credentials helper. Mistral uses an API key sent as
Authorization: Bearer. The real key never touches this script: the runtime
swaps the surrogate on approved egress, only to api.mistral.ai.

Cost: chat completions, embeddings, and OCR all bill against the key's
Mistral credits (OCR is billed per page processed). None of these are
gated with --confirm because they are ordinary API usage, not third-party
actions like dialing a phone number; the operating rules in SKILL.md state
the billing surface so callers can decide.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.mistral"
ALLOWED_HOSTS = ("api.mistral.ai",)
BASE = "https://api.mistral.ai/v1"
CONNECT_GUIDANCE = (
    "not connected: create a Mistral API key (console.mistral.ai > API "
    "keys) and collect it via the secure credential flow "
    "(credentials.request_api_access) as `custom.mistral`, then retry."
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
        sys.exit(f"error: mistral returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(args):
    call("GET", "/models")
    print(json.dumps({"ok": True,
                      "note": "credential accepted"}, indent=2))


def cmd_models(args):
    result = call("GET", "/models")
    items = result.get("data", []) if isinstance(result, dict) else result
    out = [{"id": m.get("id"), "object": m.get("object"),
            "created": m.get("created")}
           for m in items]
    print(json.dumps(out, indent=2))


def cmd_chat(args):
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})
    payload = {"model": args.model, "messages": messages}
    if args.temperature is not None:
        payload["temperature"] = args.temperature
    if args.max_tokens is not None:
        payload["max_tokens"] = args.max_tokens
    if args.json_mode:
        payload["response_format"] = {"type": "json_object"}
    result = call("POST", "/chat/completions", payload)
    choices = result.get("choices", [])
    text = choices[0]["message"]["content"] if choices else None
    print(json.dumps({
        "text": text,
        "model": result.get("model"),
        "usage": result.get("usage"),
    }, indent=2))


def cmd_embeddings(args):
    texts = args.text
    if len(texts) == 1 and not args.full:
        preview_note = None
    payload = {"model": args.model, "input": texts}
    if args.output_dimension is not None:
        payload["output_dimension"] = args.output_dimension
    result = call("POST", "/embeddings", payload)
    data = result.get("data", [])
    out = []
    for item in data:
        vec = item.get("embedding", [])
        entry = {"index": item.get("index"), "dimensions": len(vec)}
        if args.full:
            entry["embedding"] = vec
        else:
            entry["preview"] = vec[:8]
        out.append(entry)
    print(json.dumps({"model": result.get("model"), "usage": result.get("usage"),
                      "data": out,
                      "note": "re-run with --full to print complete vectors"
                              if not args.full else None}, indent=2))


def cmd_ocr(args):
    if args.document_url:
        document = {"type": "document_url",
                    "document_url": args.document_url}
    elif args.image_url:
        document = {"type": "image_url",
                    "image_url": args.image_url}
    else:
        sys.exit("error: one of --document-url or --image-url is required")
    payload = {"model": args.model, "document": document}
    if args.pages:
        payload["pages"] = [int(p) for p in args.pages.split(",")
                            if p.strip().isdigit()]
    if args.include_image_base64:
        payload["include_image_base64"] = True
    if args.image_limit is not None:
        payload["image_limit"] = args.image_limit
    if args.image_min_size is not None:
        payload["image_min_size"] = args.image_min_size
    result = call("POST", "/ocr", payload)
    pages = result.get("pages", [])
    out = []
    for p in pages:
        entry = {"index": p.get("index"), "markdown": p.get("markdown"),
                 "dimensions": p.get("dimensions")}
        if args.include_images:
            entry["images"] = p.get("images")
        out.append(entry)
    print(json.dumps({"model": result.get("model"),
                      "pages_processed": (result.get("usage_info") or {}).get(
                          "pages_processed"),
                      "usage_info": result.get("usage_info"),
                      "pages": out}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Mistral AI (La Plateforme) API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("models", help="list models available to the API key")
    p.set_defaults(func=cmd_models)

    p = sub.add_parser("chat", help="run a chat completion (bills credits)")
    p.add_argument("--model", default="mistral-large-latest",
                   help="model id; use `models` to list current ids")
    p.add_argument("--prompt", "--message", dest="prompt", required=True,
                   help="the user message text")
    p.add_argument("--system", default=None, help="system prompt")
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--max-tokens", type=int, default=None)
    p.add_argument("--json-mode", action="store_true",
                   help="request JSON object response format")
    p.set_defaults(func=cmd_chat)

    p = sub.add_parser("embeddings",
                       help="create text embeddings (bills credits)")
    p.add_argument("--model", default="mistral-embed",
                   help="embedding model id; mistral-embed (1024 dims)")
    p.add_argument("--text", action="append", required=True,
                   help="text to embed; repeat for multiple inputs")
    p.add_argument("--output-dimension", type=int, default=None,
                   help="truncate embeddings to this many dimensions")
    p.add_argument("--full", action="store_true",
                   help="print complete vectors instead of previews")
    p.set_defaults(func=cmd_embeddings)

    p = sub.add_parser("ocr",
                       help="extract text/markdown from a document or image "
                            "with the OCR API (billed per page processed)")
    p.add_argument("--model", default="mistral-ocr-latest",
                   help="OCR model id")
    p.add_argument("--document-url", default=None,
                   help="URL of a PDF or image document to OCR")
    p.add_argument("--image-url", default=None,
                   help="URL of a single image to OCR")
    p.add_argument("--pages", default=None,
                   help="comma-separated page indices to OCR, e.g. '0,1'")
    p.add_argument("--include-image-base64", action="store_true",
                   help="return extracted images as base64 in the payload")
    p.add_argument("--include-images", action="store_true",
                   help="print the page image blocks in the output")
    p.add_argument("--image-limit", type=int, default=None,
                   help="max number of images to extract per page")
    p.add_argument("--image-min-size", type=int, default=None,
                   help="minimum size of images to extract")
    p.set_defaults(func=cmd_ocr)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
