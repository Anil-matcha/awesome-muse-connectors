#!/usr/bin/env python3
"""Minimal Replicate API CLI for the muse-connectors replicate skill.

Auth: loads the per-user `custom.replicate` credential as a surrogate via the
bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.replicate.com.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.replicate"
ALLOWED_HOSTS = ("api.replicate.com",)
API = "https://api.replicate.com/v1"

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
            detail = body.get("detail", body.get("error", str(exc)))
        except Exception:
            detail = str(exc)
        sys.exit(f"error: Replicate returned HTTP {exc.code}: {detail}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def summarize_prediction(pred: dict) -> dict:
    return {"id": pred.get("id"), "version": pred.get("version"),
            "status": pred.get("status"), "created_at": pred.get("created_at"),
            "completed_at": pred.get("completed_at"),
            "error": pred.get("error"), "output": pred.get("output")}


def cmd_auth(_args):
    result = call("GET", "/predictions", params={"limit": 1})
    results = result.get("results", [])
    print(json.dumps({"ok": True,
                      "recent_predictions": len(results)}, indent=2))


def cmd_model(args):
    result = call("GET", f"/models/{args.name}")
    latest = result.get("latest_version", {})
    input_schema = None
    schema = (latest.get("openapi_schema") or {}).get("components", {}).get("schemas", {})
    if isinstance(schema, dict) and "Input" in schema:
        input_schema = schema["Input"]
    print(json.dumps({"name": result.get("name"),
                      "description": result.get("description"),
                      "latest_version_id": latest.get("id"),
                      "input_schema": input_schema}, indent=2))


def cmd_predict(args):
    try:
        inputs = json.loads(args.input_json)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --input-json is not valid JSON: {exc}")
    if not isinstance(inputs, dict):
        sys.exit("error: --input-json must be a JSON object")
    payload = {"version": args.version, "input": inputs}
    result = call("POST", "/predictions", payload=payload)
    print(json.dumps(summarize_prediction(result), indent=2))


def cmd_status(args):
    result = call("GET", f"/predictions/{args.id}")
    print(json.dumps(summarize_prediction(result), indent=2))


def cmd_cancel(args):
    result = call("POST", f"/predictions/{args.id}/cancel")
    print(json.dumps({"ok": True, "id": result.get("id"),
                      "status": result.get("status")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Replicate API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("model", help="look up a model version and input schema")
    p.add_argument("--name", required=True,
                   help="owner/name, e.g. stability-ai/sdxl")
    p.set_defaults(func=cmd_model)

    p = sub.add_parser("predict", help="create a prediction (async; confirm first)")
    p.add_argument("--version", required=True, help="model version ID")
    p.add_argument("--input-json", required=True,
                   help='model inputs as a JSON object string, e.g. \'{"prompt": "..."}\'')
    p.set_defaults(func=cmd_predict)

    p = sub.add_parser("status", help="poll a prediction by ID")
    p.add_argument("--id", required=True, help="prediction ID")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("cancel", help="cancel a prediction (confirm first)")
    p.add_argument("--id", required=True, help="prediction ID")
    p.set_defaults(func=cmd_cancel)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
