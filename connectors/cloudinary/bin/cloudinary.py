#!/usr/bin/env python3
"""Minimal Cloudinary Upload + Admin API CLI for the muse-connectors Cloudinary skill.

Auth: three values are needed (cloud_name, api_key, api_secret). They are
collected as one colon-joined value and stored as three named entries
(`cloud_name`, `api_key`, `api_secret`) under `custom.cloudinary`, loaded as
surrogates via the bundled dynamic_credentials helper. The CLI splits them
at use:

- cloud_name goes into the request host: https://api.cloudinary.com/v1_1/{cloud_name}
- api_key:api_secret go into HTTP Basic auth: Authorization: Basic base64(api_key:api_secret)

following the same surrogate-in-Basic-header pattern as the ashby connector.
The real values never touch this script: the runtime swaps the surrogates on
approved egress, only to api.cloudinary.com.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.cloudinary"
ALLOWED_HOSTS = ("api.cloudinary.com",)
API_HOST = "https://api.cloudinary.com"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        dynamic_credential_entry,
        ensure_allowed_url,
        read_json_response,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def credential_error(exc: Exception) -> None:
    sys.exit(
        "error: no stored credential for custom.cloudinary "
        f"({exc}). To connect, ask Muse to connect Cloudinary via the secure "
        "credential flow (one colon-joined value: cloud_name:api_key:api_secret, "
        "from the Cloudinary Console at Settings, API Keys), then retry."
    )


def load_credential() -> tuple[str, str]:
    """Return (base_url, basic_auth_header) built from the three surrogates."""
    try:
        cloud_name = dynamic_credential_entry(CREDENTIAL_NAME, "cloud_name")["surrogate"]
        api_key = dynamic_credential_entry(CREDENTIAL_NAME, "api_key")["surrogate"]
        api_secret = dynamic_credential_entry(CREDENTIAL_NAME, "api_secret")["surrogate"]
    except (DynamicCredentialError, OSError) as exc:
        credential_error(exc)
    base_url = f"{API_HOST}/v1_1/{urllib.parse.quote(str(cloud_name).strip(), safe='')}"
    token = base64.b64encode(f"{api_key}:{api_secret}".encode("utf-8")).decode("ascii")
    return base_url, f"Basic {token}"


def api_error(exc: urllib.error.HTTPError) -> None:
    try:
        body = json.loads(exc.read().decode("utf-8", errors="replace"))
        err = body.get("error")
        msg = err.get("message") if isinstance(err, dict) else (err or str(exc))
    except Exception:
        msg = str(exc)
    sys.exit(f"error: cloudinary returned HTTP {exc.code}: {msg}")


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None, raw: bytes | None = None,
         content_type: str | None = None) -> dict:
    base_url, auth_header = load_credential()
    url = base_url + path
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None})
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    data = raw
    headers = {"Authorization": auth_header}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
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
    result = call("GET", "/usage")
    print(json.dumps({"ok": True, "plan": result.get("plan"),
                      "credits": result.get("credits")}, indent=2))


def cmd_usage(_args):
    print(json.dumps(call("GET", "/usage"), indent=2))


def cmd_upload(args):
    try:
        with open(args.file, "rb") as fh:
            content = fh.read()
    except OSError as exc:
        sys.exit(f"error: cannot read file: {exc}")
    fields: dict[str, str] = {}
    if args.folder:
        fields["folder"] = args.folder
    if args.public_id:
        fields["public_id"] = args.public_id
    body, ctype = encode_multipart(
        fields,
        {"file": (args.file.split("/")[-1], content, "application/octet-stream")},
    )
    result = call("POST", f"/{args.resource_type}/upload", raw=body, content_type=ctype)
    print(json.dumps({
        "public_id": result.get("public_id"),
        "secure_url": result.get("secure_url"),
        "resource_type": result.get("resource_type"),
        "bytes": result.get("bytes"),
    }, indent=2))


def cmd_list(args):
    result = call("GET", "/resources/image",
                  params={"prefix": args.prefix, "max_results": args.max_results,
                          "next_cursor": args.next_cursor})
    resources = [
        {"public_id": r.get("public_id"), "format": r.get("format"),
         "bytes": r.get("bytes"), "secure_url": r.get("secure_url"),
         "created_at": r.get("created_at")}
        for r in result.get("resources", [])
    ]
    print(json.dumps({"resources": resources,
                      "next_cursor": result.get("next_cursor")}, indent=2))


def cmd_get(args):
    result = call("GET", f"/resources/image/upload/{urllib.parse.quote(args.public_id, safe='')}")
    print(json.dumps(result, indent=2))


def cmd_update(args):
    try:
        payload = json.loads(args.data)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --data is not valid JSON: {exc}")
    result = call("POST", f"/resources/image/upload/{urllib.parse.quote(args.public_id, safe='')}",
                  payload=payload)
    print(json.dumps({"public_id": result.get("public_id"),
                      "tags": result.get("tags")}, indent=2))


def cmd_delete(args):
    result = call("DELETE", f"/resources/image/upload/{urllib.parse.quote(args.public_id, safe='')}")
    print(json.dumps({"deleted": result.get("result") == "ok",
                      "public_id": args.public_id}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Cloudinary Upload + Admin API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the connection (shows plan usage)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("usage", help="plan usage: credits, storage, bandwidth, transformations")
    p.set_defaults(func=cmd_usage)

    p = sub.add_parser("upload", help="upload an image or video")
    p.add_argument("--file", required=True, help="local file path")
    p.add_argument("--resource-type", default="image", choices=["image", "video", "raw"])
    p.add_argument("--folder", default=None, help="destination folder")
    p.add_argument("--public-id", default=None, help="explicit public id")
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("list", help="list image assets")
    p.add_argument("--prefix", default=None)
    p.add_argument("--max-results", default=None)
    p.add_argument("--next-cursor", default=None)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("get", help="asset details")
    p.add_argument("--public-id", required=True)
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("update", help="update metadata/tags")
    p.add_argument("--public-id", required=True)
    p.add_argument("--data", required=True,
                   help="raw JSON body per the Cloudinary Admin API docs")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("delete", help="delete an asset")
    p.add_argument("--public-id", required=True)
    p.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
