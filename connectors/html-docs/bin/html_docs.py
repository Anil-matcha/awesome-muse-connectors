#!/usr/bin/env python3
"""HTML Docs Collaboration API CLI for the Muse html-docs connector.

Auth: loads the per-user `custom.html-docs` credential as a surrogate through
Muse's bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate on approved egress, only to
www.html-docs.com.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.html-docs"
ALLOWED_HOSTS = ("www.html-docs.com",)
API_BASE = "https://www.html-docs.com/api/v1"
CONNECT_GUIDANCE = (
    "not connected: create a dedicated HTML Docs API key at "
    "https://www.html-docs.com/settings/api-keys and collect it through the "
    "secure credential flow (credentials.request_api_access) as "
    "`custom.html-docs`, then retry"
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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so credentials never travel to another destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def segment(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("invalid document or block identifier")
    return value


def call(method: str, path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    if body is not None and len(body) > 2 * 1024 * 1024:
        raise ValueError("request exceeds 2 MB; split the document into smaller parts")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-agent-name": "Muse",
    }
    req = urllib.request.Request(
        API_BASE + path, data=body, method=method, headers=headers
    )
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        detail = str(exc).lower()
        if "missing" in detail or "surrogate" in detail:
            sys.exit(CONNECT_GUIDANCE)
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=60) as response:
            return read_json_response(response)
    except urllib.error.HTTPError as exc:
        messages = {
            401: "reconnect HTML Docs through Muse's secure credential flow",
            403: "credential rejected or account does not have permission",
            404: "document or block not found; check the identifier",
            429: "rate limited; wait and check the write outcome before retrying",
        }
        message = messages.get(
            exc.code,
            "request failed; check the current state before retrying a write",
        )
        retry_after = exc.headers.get("Retry-After", "")
        result: dict = {"error": message, "status": exc.code}
        if retry_after.isdigit():
            result["retry_after_seconds"] = int(retry_after)
        sys.exit(json.dumps(result))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        sys.exit(
            json.dumps(
                {
                    "error": (
                        "no valid response received; check the current state "
                        "before retrying a write"
                    )
                }
            )
        )


def file_content(filename: str) -> str:
    content = Path(filename).read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError("input file is empty")
    return content


def require_confirmation(args: argparse.Namespace) -> None:
    if not args.confirm:
        raise ValueError(
            "write not confirmed; show the exact change to the user and rerun with --confirm"
        )


def redact_sensitive(value):
    if isinstance(value, dict):
        return {
            key: redact_sensitive(item)
            for key, item in value.items()
            if key not in {"token", "share_token", "editUrl", "edit_url"}
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def execute(args: argparse.Namespace):
    if args.command == "auth":
        call("GET", "/docs?limit=1&offset=0")
        return {"ok": True, "note": "credential accepted"}
    if args.command == "list":
        if not 1 <= args.limit <= 200 or args.offset < 0:
            raise ValueError("use limit 1-200 and a non-negative offset")
        query = urllib.parse.urlencode({"limit": args.limit, "offset": args.offset})
        return call("GET", "/docs?" + query)
    if args.command == "search":
        query_text = args.query.strip()
        if not 2 <= len(query_text) <= 200:
            raise ValueError("search queries must contain 2-200 characters")
        query = {"q": query_text}
        if args.workspace:
            query["workspace"] = args.workspace
        return call("GET", "/search?" + urllib.parse.urlencode(query))
    if args.command == "create":
        require_confirmation(args)
        payload = {"title": args.title, args.format: file_content(args.file)}
        return call("POST", "/docs", payload)

    path = "/docs/" + segment(args.document_id)
    if args.command == "read":
        return call("GET", path)
    if args.command in ("blocks", "comments"):
        return call("GET", path + "/" + args.command)

    require_confirmation(args)
    payload = {"content": file_content(args.file)}
    if args.command == "update-block":
        return call(
            "PATCH",
            path + "/blocks/" + segment(args.region_key),
            payload,
        )
    if args.region_key:
        payload["region_key"] = segment(args.region_key)
    return call("POST", path + "/comments", payload)


def build_parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("auth", help="verify the credential")

    listing = commands.add_parser("list", help="list accessible documents")
    listing.add_argument("--limit", type=int, default=20)
    listing.add_argument("--offset", type=int, default=0)

    search = commands.add_parser("search", help="search accessible documents")
    search.add_argument("query")
    search.add_argument("--workspace")

    create = commands.add_parser("create", help="create a private document")
    create.add_argument("--title", required=True)
    create.add_argument("--file", required=True)
    create.add_argument("--format", choices=["html", "markdown"], default="html")
    create.add_argument("--confirm", action="store_true")

    for name in ("read", "blocks", "comments", "update-block", "comment"):
        command = commands.add_parser(name)
        command.add_argument("document_id")
        if name == "update-block":
            command.add_argument("region_key")
        if name == "comment":
            command.add_argument("--region-key")
        if name in ("update-block", "comment"):
            command.add_argument("--file", required=True)
            command.add_argument("--confirm", action="store_true")
    return result


def main() -> int:
    args = build_parser().parse_args()
    try:
        print(json.dumps(redact_sensitive(execute(args)), ensure_ascii=False, indent=2))
        return 0
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
    except OSError:
        print(json.dumps({"error": "could not read the input file"}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
