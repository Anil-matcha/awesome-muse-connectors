#!/usr/bin/env python3
"""Minimal VEED direct-API CLI for the muse-connectors veed skill.

Auth: loads the per-user `custom.veed` credential as a surrogate via the
bundled dynamic_credentials helper. VEED's direct API uses
`Authorization: Bearer <API_KEY>`. The real key never touches this script:
the runtime swaps the surrogate on approved egress, only to the host given
via --api-host.

IMPORTANT: VEED publishes the background-removal path
(`POST /v1/video/background-remove`) but no base host in its public docs;
veed.io/api currently routes new developers through fal.ai. This CLI takes
--api-host explicitly and never guesses it. Confirm the host from VEED's
developer documentation or your VEED API dashboard before use. The
fal.ai-hosted VEED models (veed/lipsync, veed/fabric-1.0) are covered by the
separate fal-ai connector, not here.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import urllib.parse
import urllib.request
import uuid

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.veed"

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


def get_surrogate() -> str:
    try:
        entry = dynamic_credential_entry(CREDENTIAL_NAME)
    except DynamicCredentialError:
        sys.exit(
            f"not connected: no `{CREDENTIAL_NAME}` credential is stored.\n"
            "Connect it with the secure credential flow (see this skill's "
            "Auth section), then retry."
        )
    return str(entry["surrogate"]).strip()


def resolve_host(api_host: str | None) -> tuple[str, tuple[str, ...]]:
    if not api_host:
        sys.exit(
            "error: --api-host is required. VEED does not publish a default "
            "API base host in its public docs; confirm the host from VEED's "
            "developer documentation or your VEED API dashboard, e.g.\n"
            "  bin/veed.py background-remove --api-host https://<host> --file in.mp4"
        )
    parsed = urllib.parse.urlparse(api_host)
    if parsed.scheme != "https" or not parsed.hostname:
        sys.exit("error: --api-host must be an https URL with a hostname")
    base = f"https://{parsed.hostname}"
    if parsed.port:
        base += f":{parsed.port}"
    return base.rstrip("/"), (parsed.hostname,)


def encode_multipart(fields: dict, file_field: str, file_path: str) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        body += f"{value}\r\n".encode()
    with open(file_path, "rb") as fh:
        file_bytes = fh.read()
    filename = file_path.split("/")[-1]
    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    body += f"--{boundary}\r\n".encode()
    body += (f'Content-Disposition: form-data; name="{file_field}"; '
             f'filename="{filename}"\r\n').encode()
    body += f"Content-Type: {content_type}\r\n\r\n".encode()
    body += file_bytes + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def authed_post_multipart(url: str, allowed_hosts: tuple[str, ...],
                          body: bytes, content_type: str) -> dict:
    ensure_allowed_url(url, allowed_hosts=allowed_hosts)
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": content_type,
                                          "Content-Length": str(len(body))})
    req.add_header("Authorization", f"Bearer {get_surrogate()}")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            msg = json.loads(raw).get("message", raw[:500])
        except Exception:
            msg = str(exc)
        sys.exit(f"error: veed returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(args):
    base, _ = resolve_host(args.api_host)
    get_surrogate()  # raises with connect guidance if missing
    print(json.dumps({
        "ok": True,
        "api_host": base,
        "note": "credential is stored and the host is set; the key was not "
                "verified because VEED's direct API has no free status "
                "endpoint (every background-removal call is metered).",
    }, indent=2))


def cmd_background_remove(args):
    base, allowed_hosts = resolve_host(args.api_host)
    fields = {"endpoint": args.endpoint, "output_format": args.output_format}
    if args.resolution:
        fields["resolution"] = args.resolution
    if args.webhook_url:
        fields["webhook_url"] = args.webhook_url
    body, content_type = encode_multipart(fields, "file", args.file)
    result = authed_post_multipart(base + "/v1/video/background-remove",
                                   allowed_hosts, body, content_type)
    output = {
        "status": result.get("status"),
        "output_url": result.get("output_url"),
        "format": result.get("format"),
        "resolution": result.get("resolution"),
        "duration_seconds": result.get("duration_seconds"),
    }
    print(json.dumps(output, indent=2))
    if result.get("output_url"):
        print("note: the output URL is time-limited; download the processed "
              "video promptly, do not store the URL.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="VEED direct API CLI (muse-connectors)")
    parser.add_argument("--api-host",
                        help="VEED direct API base host (https URL); required, never defaulted")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="check readiness (credential + host; no free status endpoint exists)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("background-remove",
                       help="remove video background (confirm first: every call is metered)")
    p.add_argument("--file", required=True, help="local video file")
    p.add_argument("--endpoint", default="standard",
                   choices=["standard", "fast", "green_screen"],
                   help="standard (quality), fast (throughput), green_screen (chroma key)")
    p.add_argument("--output-format", default="vp9_alpha",
                   choices=["vp9_alpha", "h264_rgba"])
    p.add_argument("--resolution", help="e.g. 4k (default: source resolution)")
    p.add_argument("--webhook-url", help="webhook for async completion of long jobs")
    p.set_defaults(func=cmd_background_remove)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
