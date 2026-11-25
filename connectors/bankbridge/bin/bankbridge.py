#!/usr/bin/env python3
"""BankBridge CLI for the muse-connectors bankbridge skill.

BankBridge (https://bankbridge.money) is a hosted, read-only MCP server for
bank accounts, transactions and investment holdings. This CLI calls its
documented tools over the Streamable HTTP endpoint (JSON-RPC `tools/call`).

Auth: a BankBridge API key (`bbk_...`, created in the BankBridge dashboard) is
sent only in the `Authorization: Bearer` header. On a Muse runtime the per-user
`custom.bankbridge` credential is loaded as a surrogate via the bundled
dynamic_credentials helper, so the real key never touches this script.
Outside Muse the key is read from the BANKBRIDGE_API_KEY environment variable.
The key is never accepted as an argument. The public demo key `bbk_demo`
returns sample data for a made-up user.

Every tool is read-only. Nothing here moves money.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.bankbridge"
ENV_KEY = "BANKBRIDGE_API_KEY"
ALLOWED_HOSTS = ("bankbridge.money",)
ENDPOINT = "https://bankbridge.money/api/mcp"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import DynamicCredentialError, add_surrogate_to_request
except ImportError:  # not on a Muse runtime: env var only
    DynamicCredentialError = Exception
    add_surrogate_to_request = None

# command -> (tool name, [(flag, arg name, type)], positional [(arg name, type)])
TOOLS = {
    "accounts": ("list_accounts", [], []),
    "account": ("get_account", [], [("account_id", str)]),
    "transactions": ("list_transactions", [
        ("--account-id", "account_id", str), ("--start", "start_date", str),
        ("--end", "end_date", str), ("--min-amount", "min_amount", float),
        ("--max-amount", "max_amount", float), ("--category", "category", str),
        ("--pending", "pending", "bool"), ("--limit", "limit", int),
        ("--offset", "offset", int)], []),
    "search": ("search_transactions", [
        ("--account-id", "account_id", str), ("--start", "start_date", str),
        ("--end", "end_date", str), ("--limit", "limit", int),
        ("--offset", "offset", int)], [("query", str)]),
    "spending": ("get_spending_summary", [
        ("--group-by", "group_by", str), ("--account-id", "account_id", str),
        ("--start", "start_date", str), ("--end", "end_date", str),
        ("--limit", "limit", int)], []),
    "recurring": ("get_recurring_charges", [
        ("--account-id", "account_id", str), ("--start", "start_date", str),
        ("--end", "end_date", str), ("--min-occurrences", "min_occurrences", int)], []),
    "cashflow": ("get_monthly_cashflow", [
        ("--account-id", "account_id", str)], [("month", str)]),
    "merchant": ("get_merchant_history", [
        ("--account-id", "account_id", str), ("--start", "start_date", str),
        ("--end", "end_date", str), ("--limit", "limit", int),
        ("--offset", "offset", int)], [("merchant", str)]),
    "categories": ("list_categories", [
        ("--start", "start_date", str), ("--end", "end_date", str)], []),
    "holdings": ("list_holdings", [
        ("--account-id", "account_id", str), ("--limit", "limit", int),
        ("--offset", "offset", int)], []),
    "investment-transactions": ("list_investment_transactions", [
        ("--account-id", "account_id", str), ("--type", "type", str),
        ("--subtype", "subtype", str), ("--start", "start_date", str),
        ("--end", "end_date", str), ("--limit", "limit", int),
        ("--offset", "offset", int)], []),
    "connect-link": ("connect_bank", [], []),
}


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


def attach_key(req: urllib.request.Request) -> None:
    key = os.environ.get(ENV_KEY, "").strip()
    if any(ch.isspace() or not ch.isprintable() for ch in key):
        sys.exit(f"error: {ENV_KEY} contains whitespace or control characters")
    if key:
        req.add_header("Authorization", "Bearer " + key)
        return
    if add_surrogate_to_request is not None:
        try:
            add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
            return
        except DynamicCredentialError as exc:
            sys.exit(f"error: credential problem: {exc}")
    sys.exit(
        f"error: no BankBridge key (set {ENV_KEY}, or connect custom.bankbridge in Muse)"
    )


def parse_response(raw: str) -> dict:
    """The endpoint answers with JSON or a single SSE `data:` event."""
    raw = raw.strip()
    if raw.startswith("{"):
        return json.loads(raw)
    for line in raw.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    sys.exit(f"error: unexpected response from bankbridge: {raw[:300]}")


def call_tool(name: str, arguments: dict) -> None:
    check_url(ENDPOINT)
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": arguments}}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"})
    attach_key(req)
    try:
        with OPENER.open(req, timeout=60) as resp:
            msg = parse_response(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        sys.exit(f"error: bankbridge returned HTTP {exc.code}: {text[:400]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")
    if "error" in msg:
        sys.exit(f"error: bankbridge: {json.dumps(msg['error'])[:400]}")
    result = msg.get("result", {})
    text = "".join(c.get("text", "") for c in result.get("content", []))
    if result.get("isError"):
        sys.exit(f"error: bankbridge tool error: {text[:400]}")
    try:
        print(json.dumps(json.loads(text), indent=2))
    except ValueError:
        print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="BankBridge read-only bank data")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth", help="verify the key by listing accounts")
    for cmd, (_tool, flags, positionals) in TOOLS.items():
        p = sub.add_parser(cmd)
        for arg, typ in positionals:
            p.add_argument(arg, type=typ)
        for flag, dest, typ in flags:
            if typ == "bool":
                p.add_argument(flag, dest=dest, choices=["true", "false"])
            else:
                p.add_argument(flag, dest=dest, type=typ)
    args = parser.parse_args()
    if args.cmd == "auth":
        call_tool("list_accounts", {})
        return
    tool, flags, positionals = TOOLS[args.cmd]
    arguments = {}
    for name in [d for _, d, _ in flags] + [a for a, _ in positionals]:
        value = getattr(args, name, None)
        if value is not None:
            arguments[name] = (value == "true") if name == "pending" else value
    call_tool(tool, arguments)


if __name__ == "__main__":
    main()
