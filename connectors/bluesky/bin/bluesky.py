#!/usr/bin/env python3
"""Minimal Bluesky (AT Protocol) CLI for the muse-connectors bluesky skill.

Auth: loads the per-user `custom.bluesky` credential (a Bluesky APP PASSWORD,
never the main password) as a surrogate via the bundled dynamic_credentials
helper. The real password never touches this script: the runtime swaps the
surrogate on approved egress. Session tokens (accessJwt/refreshJwt) are
cached at <skill-dir>/.bluesky-session.json (chmod 600) so createSession is
only called when needed (rate cap 30/5min); refreshJwt is used to recover
from a 401, retrying the call once.

PDS resolution: accounts on *.bsky.social use https://bsky.social directly;
other handles are resolved via unauthenticated resolveHandle on
public.api.bsky.app plus the DID doc from plc.directory. If resolution
fails, falls back to https://bsky.social with a warning.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.bluesky"
DEFAULT_PDS = "https://bsky.social"
RESOLVE_API = "https://public.api.bsky.app"
PLC_DIRECTORY = "https://plc.directory"
SESSION_FILE_NAME = ".bluesky-session.json"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        dynamic_credential_entry,
        ensure_allowed_url,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def http_json(method: str, url: str, allowed_hosts: tuple[str, ...],
              headers: dict | None = None, payload: dict | None = None,
              params: dict | None = None) -> dict:
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    hdrs = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    ensure_allowed_url(url, allowed_hosts=allowed_hosts)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", body.get("error", str(exc)))
        except Exception:
            msg = str(exc)
        raise BlueskyHTTPError(exc.code, msg) from exc
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


class BlueskyHTTPError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(f"HTTP {code}: {message}")
        self.code = code
        self.message = message


def session_path(handle: str) -> Path:
    skill_dir = Path(__file__).resolve().parent.parent
    candidate = skill_dir / SESSION_FILE_NAME
    try:
        candidate.touch(exist_ok=True)
        os.chmod(candidate, 0o600)
        return candidate
    except OSError:
        digest = hashlib.sha256(handle.encode()).hexdigest()[:16]
        fallback = Path(tempfile.gettempdir()) / f"bluesky-session-{digest}.json"
        if fallback.exists():
            os.chmod(fallback, 0o600)
        return fallback


def load_session(handle: str) -> dict | None:
    path = session_path(handle)
    if not path.exists():
        return None
    try:
        sess = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if sess.get("handle") != handle:
        return None
    return sess


def save_session(sess: dict) -> None:
    path = session_path(sess["handle"])
    path.write_text(json.dumps(sess, indent=2))
    os.chmod(path, 0o600)


def jwt_expired(token: str) -> bool:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload).decode())
        exp = data.get("exp")
        return bool(exp) and exp < time.time() + 60
    except Exception:
        return False  # can't tell; try it and refresh on 401


def resolve_pds(handle: str) -> tuple[str, tuple[str, ...]]:
    """Return (pds_base_url, allowed_hosts) for an account handle."""
    allowed = {"bsky.social", "public.api.bsky.app", "plc.directory"}
    if handle.lower().endswith(".bsky.social"):
        return DEFAULT_PDS, tuple(allowed)
    try:
        result = http_json(
            "GET", f"{RESOLVE_API}/xrpc/com.atproto.identity.resolveHandle",
            allowed_hosts=tuple(allowed), params={"handle": handle})
        did = result.get("did")
        if not did:
            raise ValueError("no did in resolveHandle response")
        doc = http_json("GET", f"{PLC_DIRECTORY}/{did}",
                        allowed_hosts=tuple(allowed))
        pds = None
        for svc in doc.get("service", []) or []:
            if svc.get("type") == "AtprotoPersonalDataServer":
                pds = svc.get("serviceEndpoint")
                break
        if not pds:
            raise ValueError("no PDS service in DID doc")
        host = urllib.parse.urlparse(pds).hostname
        allowed.add(host)
        return pds.rstrip("/"), tuple(allowed)
    except Exception as exc:
        sys.stderr.write(
            f"warning: PDS resolution failed ({exc}); falling back to {DEFAULT_PDS}\n")
        return DEFAULT_PDS, tuple(allowed)


def create_session(handle: str, pds: str, allowed: tuple[str, ...]) -> dict:
    try:
        surrogate = dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    result = http_json(
        "POST", f"{pds}/xrpc/com.atproto.server.createSession",
        allowed_hosts=allowed,
        payload={"identifier": handle, "password": surrogate})
    sess = {
        "handle": handle,
        "did": result.get("did"),
        "pds": pds,
        "accessJwt": result.get("accessJwt"),
        "refreshJwt": result.get("refreshJwt"),
    }
    if not sess["accessJwt"] or not sess["did"]:
        sys.exit("error: createSession did not return a session")
    save_session(sess)
    return sess


def refresh_session(sess: dict, allowed: tuple[str, ...]) -> dict:
    result = http_json(
        "POST", f"{sess['pds']}/xrpc/com.atproto.server.refreshSession",
        allowed_hosts=allowed,
        headers={"Authorization": f"Bearer {sess['refreshJwt']}"})
    sess["accessJwt"] = result.get("accessJwt", sess["accessJwt"])
    sess["refreshJwt"] = result.get("refreshJwt", sess["refreshJwt"])
    save_session(sess)
    return sess


def get_session(handle: str) -> tuple[dict, tuple[str, ...]]:
    pds, allowed = resolve_pds(handle)
    sess = load_session(handle)
    if sess and sess.get("accessJwt") and not jwt_expired(sess["accessJwt"]):
        sess["pds"] = pds  # keep the freshly resolved PDS
        return sess, allowed
    if sess and sess.get("refreshJwt"):
        try:
            return refresh_session(sess, allowed), allowed
        except BlueskyHTTPError:
            pass
    return create_session(handle, pds, allowed), allowed


def xrpc(handle: str, nsid: str, method: str = "GET",
         params: dict | None = None, payload: dict | None = None) -> dict:
    sess, allowed = get_session(handle)
    url = f"{sess['pds']}/xrpc/{nsid}"
    try:
        return http_json(method, url, allowed_hosts=allowed,
                         headers={"Authorization": f"Bearer {sess['accessJwt']}"},
                         params=params, payload=payload)
    except BlueskyHTTPError as exc:
        if exc.code != 401 or not sess.get("refreshJwt"):
            sys.exit(f"error: {nsid} returned {exc}")
        refresh_session(sess, allowed)
        try:
            return http_json(method, url, allowed_hosts=allowed,
                             headers={"Authorization": f"Bearer {sess['accessJwt']}"},
                             params=params, payload=payload)
        except BlueskyHTTPError as exc2:
            sys.exit(f"error: {nsid} returned {exc2}")


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def cmd_auth(args):
    sess, _allowed = get_session(args.handle)
    profile = xrpc(args.handle, "app.bsky.actor.getProfile",
                   params={"actor": args.handle})
    print(json.dumps({"ok": True, "did": sess.get("did"),
                      "handle": profile.get("handle"),
                      "displayName": profile.get("displayName")}, indent=2))


def cmd_profile(args):
    target = args.target or args.handle
    profile = xrpc(args.handle, "app.bsky.actor.getProfile",
                   params={"actor": target})
    print(json.dumps({
        "did": profile.get("did"), "handle": profile.get("handle"),
        "displayName": profile.get("displayName"),
        "description": profile.get("description"),
        "followersCount": profile.get("followersCount"),
        "followsCount": profile.get("followsCount"),
        "postsCount": profile.get("postsCount")}, indent=2))


def cmd_timeline(args):
    feed = xrpc(args.handle, "app.bsky.feed.getTimeline",
                params={"limit": args.limit})
    posts = []
    for item in feed.get("feed", []) or []:
        post = item.get("post", {})
        record = post.get("record", {}) or {}
        author = post.get("author", {}) or {}
        posts.append({
            "uri": post.get("uri"),
            "author": author.get("handle"),
            "text": record.get("text"),
            "createdAt": record.get("createdAt"),
            "likes": post.get("likeCount"), "reposts": post.get("repostCount")})
    print(json.dumps(posts, indent=2))


def cmd_search(args):
    result = xrpc(args.handle, "app.bsky.feed.searchPosts",
                  params={"q": args.query, "limit": args.limit})
    posts = []
    for post in result.get("posts", []) or []:
        record = post.get("record", {}) or {}
        author = post.get("author", {}) or {}
        posts.append({
            "uri": post.get("uri"), "author": author.get("handle"),
            "text": record.get("text"), "createdAt": record.get("createdAt")})
    print(json.dumps(posts, indent=2))


def cmd_post(args):
    sess, _allowed = get_session(args.handle)
    result = xrpc(args.handle, "com.atproto.repo.createRecord", method="POST",
                  payload={"repo": sess["did"],
                           "collection": "app.bsky.feed.post",
                           "record": {"text": args.text, "createdAt": iso_now()}})
    print(json.dumps({"ok": True, "uri": result.get("uri"),
                      "cid": result.get("cid")}, indent=2))


def cmd_follow(args):
    sess, allowed = get_session(args.handle)
    # Resolve the target handle to a DID (unauthenticated call).
    resolved = http_json(
        "GET", f"{RESOLVE_API}/xrpc/com.atproto.identity.resolveHandle",
        allowed_hosts=allowed, params={"handle": args.target})
    target_did = resolved.get("did")
    if not target_did:
        sys.exit("error: could not resolve target handle to a DID")
    result = xrpc(args.handle, "com.atproto.repo.createRecord", method="POST",
                  payload={"repo": sess["did"],
                           "collection": "app.bsky.graph.follow",
                           "record": {"subject": target_did,
                                      "createdAt": iso_now()}})
    print(json.dumps({"ok": True, "uri": result.get("uri"),
                      "target": args.target}, indent=2))


def cmd_notifications(args):
    result = xrpc(args.handle, "app.bsky.notification.listNotifications",
                  params={"limit": args.limit})
    notes = []
    for n in result.get("notifications", []) or []:
        author = n.get("author", {}) or {}
        record = n.get("record", {}) or {}
        notes.append({
            "reason": n.get("reason"), "author": author.get("handle"),
            "text": record.get("text"), "indexedAt": n.get("indexedAt")})
    print(json.dumps(notes, indent=2))


def add_handle_arg(p):
    p.add_argument("--handle", required=True,
                   help="account handle, e.g. me.bsky.social")


def main():
    parser = argparse.ArgumentParser(description="Bluesky AT Protocol CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the session")
    add_handle_arg(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("profile", help="view a profile")
    add_handle_arg(p)
    p.add_argument("--target", default=None,
                   help="profile to view (default: your own handle)")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("timeline", help="home timeline")
    add_handle_arg(p)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_timeline)

    p = sub.add_parser("search", help="search posts")
    add_handle_arg(p)
    p.add_argument("--query", required=True)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("post", help="publish a post (confirm first)")
    add_handle_arg(p)
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_post)

    p = sub.add_parser("follow", help="follow an account (confirm first)")
    add_handle_arg(p)
    p.add_argument("--target", required=True, help="handle to follow")
    p.set_defaults(func=cmd_follow)

    p = sub.add_parser("notifications", help="list notifications")
    add_handle_arg(p)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_notifications)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
