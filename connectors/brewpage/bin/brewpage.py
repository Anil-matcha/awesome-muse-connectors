#!/usr/bin/env python3
"""BrewPage REST and MCP CLI for the Muse brewpage connector; no credential needed.
Owner tokens returned by publishes stay in a local 0600 state file, never printed."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSION = "0.1.0"
HOST = "brewpage.app"
API_BASE = f"https://{HOST}/api"
MCP_URL = f"https://{HOST}/mcp"
USER_AGENT = f"brewpage-muse/{VERSION}"
MAX_CONTENT = 5 * 1024 * 1024
STATE_FILE = Path(os.environ.get("BREWPAGE_MUSE_STATE", "~/.brewpage/muse-owned.json")).expanduser()
ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")
NS_RE = re.compile(r"[a-z0-9_-]{1,64}")
SECRET_KEYS = {"ownerToken", "managementLink", "manageUrl", "ownerLink", "visibilityUrl"}
FORMATS = ("html", "markdown")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so requests never leave brewpage.app."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def segment(value: str, pattern: re.Pattern, what: str) -> str:
    if not pattern.fullmatch(value):
        raise ValueError(f"invalid {what}")
    return value


def call(method: str, url: str, payload: dict | None = None, headers: dict | None = None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request_headers.update(headers or {})
    req = urllib.request.Request(url, data=body, method=method, headers=request_headers)
    if urllib.parse.urlsplit(req.full_url).hostname != HOST:
        raise ValueError("refusing a host outside the allowlist")
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        messages = {
            400: "request rejected; check the content, format and identifiers",
            403: "not the owner of this publication, or the request was refused",
            404: "publication not found; check the namespace and id",
            413: "content too large for the BrewPage limit",
            429: "rate limited; wait, then check the publication before retrying a write",
            503: "service busy; check the publication before retrying a write",
        }
        result: dict = {"error": messages.get(exc.code, "request failed; check the current state before retrying a write"), "status": exc.code}
        retry_after = exc.headers.get("Retry-After", "")
        if retry_after.isdigit():
            result["retry_after_seconds"] = int(retry_after)
        sys.exit(json.dumps(result))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        sys.exit(json.dumps({"error": "no valid response received; check the current state before retrying a write"}))


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(STATE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


def owner_token(ns: str, pid: str) -> str:
    token = load_state().get(f"{ns}/{pid}", {}).get("ownerToken")
    if not token:
        raise ValueError("no owner token stored for this publication; only pages published from this runtime can be changed")
    return token


def read_content(filename: str) -> str:
    content = Path(filename).read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError("input file is empty")
    if len(content.encode("utf-8")) > MAX_CONTENT:
        raise ValueError("content exceeds 5 MB; split it into smaller pages")
    return content


def require_confirmation(args: argparse.Namespace) -> None:
    if not args.confirm:
        raise ValueError("write not confirmed; show the exact change to the user and rerun with --confirm")


def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if k not in SECRET_KEYS}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def mcp_tools() -> dict:
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "brewpage-muse", "version": VERSION}}}
    headers = {"Accept": "application/json, text/event-stream"}
    server = call("POST", MCP_URL, init, headers).get("result", {}).get("serverInfo", {})
    tools = call("POST", MCP_URL, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers).get("result", {}).get("tools", [])
    return {"server": server, "tools": [t.get("name") for t in tools]}


def execute(args: argparse.Namespace):
    if args.command == "status":
        limits = call("GET", API_BASE + "/limits")
        return {"ok": True, "note": "no credential needed", "limitTypes": sorted(limits)}
    if args.command == "limits":
        return call("GET", API_BASE + "/limits")
    if args.command == "tools":
        return mcp_tools()
    if args.command == "owned":
        return [{"ref": ref, "link": item.get("link"), "expiresAt": item.get("expiresAt")} for ref, item in load_state().items()]

    if args.command == "publish":
        require_confirmation(args)
        query = {"ttl": str(args.ttl)}
        if args.public:
            query["ns"] = "public"
        payload = {"content": read_content(args.file), "format": args.format}
        result = call("POST", API_BASE + "/html?" + urllib.parse.urlencode(query), payload)
        state = load_state()
        ref = f"{result.get('namespace')}/{result.get('id')}"
        state[ref] = {"ownerToken": result.get("ownerToken"), "link": result.get("link"), "expiresAt": result.get("expiresAt")}
        save_state(state)
        return result

    ns = segment(args.ns, NS_RE, "namespace")
    pid = segment(args.id, ID_RE, "id")
    path = f"{API_BASE}/html/{ns}/{pid}"
    headers = {"X-Owner-Token": owner_token(ns, pid)}
    if args.command == "get":
        return call("GET", path + "/settings", None, headers)
    require_confirmation(args)
    if args.command == "update":
        payload = {"content": read_content(args.file), "format": args.format}
        return call("PUT", path, payload, headers)
    call("DELETE", path, None, headers)
    state = load_state()
    state.pop(f"{ns}/{pid}", None)
    save_state(state)
    return {"ok": True, "deleted": f"{ns}/{pid}"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="check that the API answers (no credential)")
    commands.add_parser("limits", help="upload limits per content type")
    commands.add_parser("tools", help="list the tools of the remote MCP endpoint (metadata only)")
    commands.add_parser("owned", help="pages published from this runtime (no tokens shown)")

    publish = commands.add_parser("publish", help="publish an HTML or Markdown file")
    publish.add_argument("--file", required=True)
    publish.add_argument("--format", choices=FORMATS, default="html")
    publish.add_argument("--ttl", type=int, choices=range(1, 31), default=15, metavar="DAYS")
    publish.add_argument("--public", action="store_true", help="list in the public gallery (default: unlisted)")
    publish.add_argument("--confirm", action="store_true")

    get = commands.add_parser("get", help="owner metadata of a page published from this runtime")
    get.add_argument("ns")
    get.add_argument("id")

    update = commands.add_parser("update", help="replace a page published from this runtime")
    update.add_argument("ns")
    update.add_argument("id")
    update.add_argument("--file", required=True)
    update.add_argument("--format", choices=FORMATS, default="html")
    update.add_argument("--confirm", action="store_true")

    delete = commands.add_parser("delete", help="delete a page published from this runtime")
    delete.add_argument("ns")
    delete.add_argument("id")
    delete.add_argument("--confirm", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        print(json.dumps(redact(execute(args)), ensure_ascii=False, indent=2))
        return 0
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
    except OSError:
        print(json.dumps({"error": "could not read the input file or state file"}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
