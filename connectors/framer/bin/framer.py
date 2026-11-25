#!/usr/bin/env python3
"""Minimal Framer Server API CLI for the muse-connectors Framer skill.

Framer's Server API is WebSocket/SDK-only (no REST surface). This CLI performs
the official connection handshake from the `framer-api` npm package as a
connection check:

  wss://api.framer.com/channel/headless-plugin?projectId=<id>&...
  with the header  Authorization: Token <api_key>

then waits for the server's `ready` message, answers with
`{"type":"pluginReadySignal"}`, and treats `pluginReadyResponse` as success
(an `error` message means the key/project pair was rejected).

Auth: per-project API key loaded as a surrogate for `custom.framer` via the
bundled dynamic_credentials helper. The real key never touches this script:
it travels only inside the WebSocket upgrade's Authorization header, which
the runtime swaps on approved egress, only to api.framer.com.

Deeper operations (pages, CMS, canvas, publish/deploy) run through the
official `framer-api` npm package; the plugin RPC protocol is not
reimplemented here.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.parse

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.framer"
ALLOWED_HOSTS = ("api.framer.com",)
WS_HOST = "api.framer.com"
WS_PATH = "/channel/headless-plugin"
SDK_VERSION = "5.0.0"
CLIENT_ID = "muse-connectors/1.0"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import DynamicCredentialError, dynamic_credential_entry
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def credential_error(exc: Exception) -> None:
    sys.exit(
        "error: no stored credential for custom.framer "
        f"({exc}). To connect, ask Muse to connect a Framer per-project API "
        "key (Site Settings, General) via the secure credential flow, then retry."
    )


def parse_project_id(value: str) -> str:
    """Accept a bare project id or a framer.com project URL."""
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9]{20}", value):
        return value
    try:
        url = urllib.parse.urlparse(value if "://" in value else "https://" + value)
        parts = [p for p in url.path.split("/") if p]
        for i, part in enumerate(parts):
            if part.lower() == "projects" and i + 1 < len(parts):
                slug = urllib.parse.unquote(parts[i + 1])
                m = re.search(r"--([A-Za-z0-9]{20})$", slug) or \
                    re.fullmatch(r"[A-Za-z0-9]{20}", slug)
                if m:
                    return m.group(1)
    except Exception:
        pass
    sys.exit("error: could not parse a project id from --project "
             "(expected a 20-char id or a framer.com/projects/... URL)")


def recv_exact(tls: ssl.SSLSocket, buf: bytearray, n: int, deadline: float) -> None:
    while len(buf) < n:
        remaining = deadline - time.time()
        if remaining <= 0:
            sys.exit("error: timed out waiting for the Framer server")
        tls.settimeout(remaining)
        chunk = tls.recv(65536)
        if not chunk:
            sys.exit("error: connection closed by the Framer server")
        buf.extend(chunk)


def read_text_messages(tls: ssl.SSLSocket, buf: bytearray, deadline: float):
    """Yield decoded text messages, answering pings, until deadline."""
    text_parts: list[str] = []
    while True:
        recv_exact(tls, buf, 2, deadline)
        b1, b2 = buf[0], buf[1]
        fin = b1 & 0x80
        opcode = b1 & 0x0F
        masked = b2 & 0x80
        length = b2 & 0x7F
        idx = 2
        if length == 126:
            recv_exact(tls, buf, idx + 2, deadline)
            length = int.from_bytes(bytes(buf[idx:idx + 2]), "big")
            idx += 2
        elif length == 127:
            recv_exact(tls, buf, idx + 8, deadline)
            length = int.from_bytes(bytes(buf[idx:idx + 8]), "big")
            idx += 8
        if masked:
            recv_exact(tls, buf, idx + 4, deadline)
            mask = bytes(buf[idx:idx + 4])
            idx += 4
        else:
            mask = None
        recv_exact(tls, buf, idx + length, deadline)
        payload = bytes(buf[idx:idx + length])
        del buf[:idx + length]
        if mask:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        if opcode == 0x8:  # close
            send_frame(tls, 0x8, payload)
            sys.exit("error: the Framer server closed the connection")
        if opcode == 0x9:  # ping -> pong
            send_frame(tls, 0xA, payload)
            continue
        if opcode == 0xA:  # pong
            continue
        if opcode in (0x1, 0x0):  # text / continuation
            text_parts.append(payload.decode("utf-8", errors="replace"))
            if fin:
                yield "".join(text_parts)
                text_parts = []
        # binary frames and others are ignored


def send_frame(tls: ssl.SSLSocket, opcode: int, payload: bytes) -> None:
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    n = len(payload)
    if n < 126:
        header = bytes([0x80 | opcode, 0x80 | n])
    elif n < 65536:
        header = bytes([0x80 | opcode, 0x80 | 126]) + n.to_bytes(2, "big")
    else:
        header = bytes([0x80 | opcode, 0x80 | 127]) + n.to_bytes(8, "big")
    tls.sendall(header + mask + masked)


def send_text(tls: ssl.SSLSocket, text: str) -> None:
    send_frame(tls, 0x1, text.encode("utf-8"))


def cmd_auth(args):
    project_id = parse_project_id(args.project)
    try:
        surrogate = dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]
    except (DynamicCredentialError, OSError) as exc:
        credential_error(exc)

    query = urllib.parse.urlencode({
        "projectId": project_id,
        "sdkVersion": SDK_VERSION,
        "clientId": CLIENT_ID,
    })
    ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        f"GET {WS_PATH}?{query} HTTP/1.1\r\n"
        f"Host: {WS_HOST}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {ws_key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        f"Authorization: Token {surrogate}\r\n"
        "\r\n"
    )
    deadline = time.time() + 30
    try:
        sock = socket.create_connection((WS_HOST, 443), timeout=10)
        tls = ssl.create_default_context().wrap_socket(sock, server_hostname=WS_HOST)
    except Exception as exc:
        sys.exit(f"error: could not reach {WS_HOST}: {exc}")
    try:
        tls.sendall(request.encode("ascii"))
        buf = bytearray()
        while b"\r\n\r\n" not in buf:
            recv_exact(tls, buf, len(buf) + 1, deadline)
        head = bytes(buf).split(b"\r\n\r\n", 1)[0]
        del buf[:len(head) + 4]
        status_line = head.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="replace")
        if " 101 " not in f" {status_line} ":
            sys.exit(f"error: websocket upgrade failed: {status_line.strip()} "
                     "(the API key was likely rejected)")
        signaled = False
        for message in read_text_messages(tls, buf, deadline):
            try:
                msg = json.loads(message)
            except json.JSONDecodeError:
                continue
            mtype = msg.get("type")
            if mtype == "error":
                sys.exit(f"error: framer rejected the handshake: "
                         f"{msg.get('message') or msg.get('code') or message}")
            if mtype == "ready" and not signaled:
                send_text(tls, json.dumps({"type": "pluginReadySignal"}))
                signaled = True
            elif mtype == "pluginReadyResponse":
                data = msg.get("data", msg)
                print(json.dumps({
                    "ok": True,
                    "project_id": project_id,
                    "request_id": msg.get("requestId"),
                    "session_id": msg.get("sessionId"),
                    "mode": (data.get("pluginReadyData") or {}).get("mode")
                            if isinstance(data, dict) else None,
                    "active_branch_id": msg.get("activeBranchId"),
                }, indent=2))
                try:
                    send_frame(tls, 0x8, b"")
                except Exception:
                    pass
                return
    finally:
        try:
            tls.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Framer Server API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key against a project via the official handshake")
    p.add_argument("--project", required=True,
                   help="Framer project URL or bare project id")
    p.set_defaults(func=cmd_auth)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
