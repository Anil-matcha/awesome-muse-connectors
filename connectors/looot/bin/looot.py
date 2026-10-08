#!/usr/bin/env python3
"""Minimal looot API CLI for the muse-connectors looot skill.

Auth: on a Muse runtime the per-user `custom.looot` credential is loaded as a
surrogate via the bundled dynamic_credentials helper, so the real token never
touches this script. Outside Muse, the token is read from the LOOOT_TOKEN
environment variable (the name the looot SDKs use). The token is sent only in
the `Authorization: Bearer` header and is never accepted as an argument.

Every request goes over HTTPS to api.looot.ai. `search`, `inspect`, `balance`
and `auth` are free reads. `run` spends prepaid balance; a failed run is not
charged. Run `inspect` and confirm the price with the user before `run`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.looot"
ENV_KEY = "LOOOT_TOKEN"
ALLOWED_HOSTS = ("api.looot.ai",)
API = "https://api.looot.ai"
TERMINAL = ("completed", "failed", "blocked", "stopped")

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import DynamicCredentialError, add_surrogate_to_request
except ImportError:  # not on a Muse runtime: env var only
    DynamicCredentialError = Exception
    add_surrogate_to_request = None


def check_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        sys.exit(f"error: refusing request to non-allowlisted URL: {url}")


class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only if it stays on an allowlisted HTTPS host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(SameHostRedirect)


def attach_token(req: urllib.request.Request) -> None:
    """Attach the bearer token from the environment or the Muse helper."""
    token = os.environ.get(ENV_KEY, "").strip()
    if any(ch.isspace() or not ch.isprintable() for ch in token):
        # Never echo the token itself in the error.
        sys.exit(f"error: {ENV_KEY} contains whitespace or control characters")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
        return
    if add_surrogate_to_request is not None:
        try:
            add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
            return
        except DynamicCredentialError as exc:
            sys.exit(f"error: credential problem: {exc}")
    sys.exit(
        f"error: no looot token found (set {ENV_KEY}, or connect custom.looot in Muse)"
    )


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None) -> dict:
    query = {k: v for k, v in (params or {}).items() if v is not None}
    url = API + path + ("?" + urllib.parse.urlencode(query) if query else "")
    check_url(url)
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    attach_token(req)
    try:
        with OPENER.open(req, timeout=75) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        sys.exit(f"error: looot returned HTTP {exc.code}: {body[:400]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def show(obj) -> None:
    print(json.dumps(obj, indent=2))


def cmd_auth(_args):
    result = call("GET", "/v1/balance")
    show({"ok": True, "balance": result})


def cmd_balance(_args):
    show(call("GET", "/v1/balance"))


def cmd_search(args):
    show(call("GET", "/v1/catalog/search", {"q": args.query, "limit": args.limit}))


def cmd_inspect(args):
    op = urllib.parse.quote(args.operation_id, safe="")
    show(call("GET", f"/v1/operations/{op}"))


def cmd_run(args):
    try:
        run_input = json.loads(args.input)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --input is not valid JSON: {exc}")
    if not isinstance(run_input, dict):
        sys.exit("error: --input must be a JSON object")
    payload = {
        "endpointId": args.operation_id,
        "input": run_input,
        "idempotencyKey": str(uuid.uuid4()),
    }
    wait = max(0, min(60, args.wait))
    run = call("POST", "/v1/runs", {"wait": wait}, payload)
    deadline = time.monotonic() + args.timeout
    while run.get("status") not in TERMINAL:
        run_id = run.get("runId")
        if not run_id:
            sys.exit(f"error: unexpected response: {json.dumps(run)[:400]}")
        if time.monotonic() >= deadline:
            show({"runId": run_id, "status": run.get("status"),
                  "note": "deadline reached; poll again with: "
                          f"bin/looot.py status {run_id}"})
            sys.exit(2)
        time.sleep(min(3, max(0.0, deadline - time.monotonic())))
        run = call("GET", f"/v1/runs/{urllib.parse.quote(run_id, safe='')}")
    show({k: run.get(k) for k in ("runId", "status", "result", "actualCost", "error")})
    if run.get("status") != "completed":
        sys.exit(1)


def cmd_status(args):
    show(call("GET", f"/v1/runs/{urllib.parse.quote(args.run_id, safe='')}"))


def main():
    parser = argparse.ArgumentParser(description="looot API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the token (GET /v1/balance, free)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("balance", help="show the prepaid balance (free)")
    p.set_defaults(func=cmd_balance)

    p = sub.add_parser("search", help="search the catalog by task words (free)")
    p.add_argument("query", help="what you want to do, in plain words")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("inspect", help="show an operation's price and inputs (free)")
    p.add_argument("operation_id")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("run", help="run an operation (spends balance; confirm the price first)")
    p.add_argument("operation_id", help="operation or job id from search")
    p.add_argument("--input", required=True, help="input as a JSON object")
    p.add_argument("--wait", type=int, default=30,
                   help="seconds the API waits inline, 0-60 (default 30)")
    p.add_argument("--timeout", type=int, default=120,
                   help="total seconds to poll before giving up (default 120)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("status", help="fetch a run by id (free)")
    p.add_argument("run_id")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
