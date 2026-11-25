#!/usr/bin/env python3
"""Minimal Canva Connect API CLI for the muse-connectors Canva skill.

Auth: OAuth 2.0 access token loaded as a surrogate for `custom.canva` via the
bundled dynamic_credentials helper (Bearer placement). The real token never
touches this script: the runtime swaps the surrogate on approved egress, only
to api.canva.com.

Exports are async: `export` submits the job, `export-status` polls it until
the status is `success`, then prints the download URLs.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.canva"
ALLOWED_HOSTS = ("api.canva.com",)
API = "https://api.canva.com/rest/v1"

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


def credential_error(exc: Exception) -> None:
    sys.exit(
        "error: no stored credential for custom.canva "
        f"({exc}). To connect, ask Muse to connect Canva via the secure "
        "credential flow (OAuth 2.0 authorization-code + PKCE), then retry."
    )


def api_error(exc: urllib.error.HTTPError) -> None:
    try:
        body = json.loads(exc.read().decode("utf-8", errors="replace"))
        msg = body.get("message") or body.get("error") or str(exc)
    except Exception:
        msg = str(exc)
    sys.exit(f"error: canva returned HTTP {exc.code}: {msg}")


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None, raw: bytes | None = None,
         content_type: str | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None})
    data = raw
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except (DynamicCredentialError, OSError) as exc:
        credential_error(exc)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        api_error(exc)
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def encode_multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    """Build a multipart/form-data body. files: name -> (filename, bytes, mime)."""
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
            f"\r\n\r\n{value}\r\n".encode("utf-8")
        )
    for name, (filename, content, mime) in files.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode("utf-8")
            + content + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def cmd_auth(_args):
    me = call("GET", "/users/me")
    print(json.dumps({"ok": True, "id": me.get("id"),
                      "display_name": me.get("display_name")}, indent=2))


def cmd_designs(args):
    result = call("GET", "/designs",
                  params={"query": args.query, "per_page": args.per_page})
    designs = [
        {"id": d.get("id"), "title": d.get("title"),
         "created_at": d.get("created_at"), "updated_at": d.get("updated_at"),
         "urls": d.get("urls")}
        for d in result.get("items", [])
    ]
    print(json.dumps(designs, indent=2))


def cmd_design(args):
    result = call("GET", f"/designs/{args.id}")
    print(json.dumps(result, indent=2))


def cmd_folders(_args):
    result = call("GET", "/folders")
    folders = [{"id": f.get("id"), "name": f.get("name")} for f in result.get("items", [])]
    print(json.dumps(folders, indent=2))


def cmd_folder_items(args):
    result = call("GET", f"/folders/{args.id}/items")
    print(json.dumps(result.get("items", []), indent=2))


def cmd_assets(_args):
    result = call("GET", "/assets")
    assets = [
        {"id": a.get("id"), "name": a.get("name"), "type": a.get("type"),
         "thumbnail": (a.get("thumbnail") or {}).get("url")}
        for a in result.get("items", [])
    ]
    print(json.dumps(assets, indent=2))


def cmd_create(args):
    try:
        payload = json.loads(args.data)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --data is not valid JSON: {exc}")
    result = call("POST", "/designs", payload=payload)
    design = result.get("design", {})
    print(json.dumps({"id": design.get("id"), "title": design.get("title"),
                      "urls": design.get("urls")}, indent=2))


def cmd_upload_asset(args):
    if args.file:
        try:
            with open(args.file, "rb") as fh:
                content = fh.read()
        except OSError as exc:
            sys.exit(f"error: cannot read file: {exc}")
        body, ctype = encode_multipart(
            {"name": args.name} if args.name else {},
            {"asset": (args.file.split("/")[-1], content, "application/octet-stream")},
        )
    else:
        # URL imports are plain form fields, not files.
        fields = {"asset": args.url}
        if args.name:
            fields["name"] = args.name
        body, ctype = encode_multipart(fields, {})
    result = call("POST", "/assets/upload", raw=body, content_type=ctype)
    asset = result.get("asset", {})
    print(json.dumps({"id": asset.get("id"), "name": asset.get("name"),
                      "type": asset.get("type")}, indent=2))


def cmd_export(args):
    result = call("POST", "/exports",
                  payload={"design_id": args.design_id, "format": args.format})
    job = result.get("job", {})
    print(json.dumps({"id": job.get("id"), "status": job.get("status")}, indent=2))


def cmd_export_status(args):
    result = call("GET", f"/exports/{args.id}")
    job = result.get("job", {})
    out = {"id": job.get("id"), "status": job.get("status")}
    if job.get("status") == "success":
        out["urls"] = job.get("urls")
    elif job.get("status") == "failed":
        out["error"] = job.get("error")
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Canva Connect API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("designs", help="list designs")
    p.add_argument("--query", default=None, help="search text")
    p.add_argument("--per-page", default=None, help="page size")
    p.set_defaults(func=cmd_designs)

    p = sub.add_parser("design", help="get one design")
    p.add_argument("--id", required=True, help="design id")
    p.set_defaults(func=cmd_design)

    p = sub.add_parser("folders", help="list folders")
    p.set_defaults(func=cmd_folders)

    p = sub.add_parser("folder-items", help="list items in a folder")
    p.add_argument("--id", required=True, help="folder id")
    p.set_defaults(func=cmd_folder_items)

    p = sub.add_parser("assets", help="list uploaded assets")
    p.set_defaults(func=cmd_assets)

    p = sub.add_parser("create", help="create a design")
    p.add_argument("--data", required=True,
                   help="raw JSON body per the Canva Connect docs, e.g. "
                        "'{\"design_type\":{\"type\":\"preset\",\"name\":\"presentation\"}}'")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("upload-asset", help="upload a file or import a URL as an asset")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="local file path to upload")
    group.add_argument("--url", help="remote URL to import")
    p.add_argument("--name", default=None, help="asset name")
    p.set_defaults(func=cmd_upload_asset)

    p = sub.add_parser("export", help="submit an async export job")
    p.add_argument("--design-id", required=True)
    p.add_argument("--format", default="png", help="png, jpg, pdf, pptx, mp4, gif")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("export-status", help="poll an export job")
    p.add_argument("--id", required=True, help="export job id")
    p.set_defaults(func=cmd_export_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
