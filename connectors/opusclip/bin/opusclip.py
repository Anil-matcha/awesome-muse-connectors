#!/usr/bin/env python3
"""Minimal OpusClip API CLI for the muse-connectors opusclip skill.

Auth: loads the per-user `custom.opusclip` credential as a surrogate via
the bundled dynamic_credentials helper. Per OpusClip's API reference
(help.opus.pro/api-reference), requests use
`Authorization: Bearer <API_KEY>` against https://api.opus.pro. The real
key never touches this script: the runtime swaps the surrogate on approved
egress, only to api.opus.pro.

Only endpoints pinned in OpusClip's published API reference are wrapped:
create a clip project, get a project, list a project's exportable clips,
and generate an upload link. Transcript, editing-script, export, social
copy, and scheduled publishing paths are documented by OpusClip but their
exact request shapes were not pinned, so they are not wrapped here.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.opusclip"
ALLOWED_HOSTS = ("api.opus.pro",)
API = "https://api.opus.pro"

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
            "Auth section for where to create an OpusClip API key), then retry."
        )
    return str(entry["surrogate"]).strip()


def call(method: str, path: str, payload: dict | None = None,
         params: dict | None = None, org_id: str | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    req.add_header("Authorization", f"Bearer {get_surrogate()}")
    if org_id:
        req.add_header("x-opus-org-id", org_id)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            err = body.get("error") or body.get("message") or body
            msg = json.dumps(err) if isinstance(err, (dict, list)) else str(err)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: opusclip returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def summarize_project(p: dict) -> dict:
    return {
        "id": p.get("id") or p.get("projectId"),
        "project_id": p.get("projectId"),
        "stage": p.get("stage"),
        "source_platform": p.get("sourcePlatform"),
        "created_at": p.get("createdAt"),
    }


def summarize_clip(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "title": c.get("title"),
        "duration": c.get("duration"),
        "score": c.get("viralityScore") or c.get("score"),
        "export_url": c.get("uriForExport") or c.get("exportUrl"),
    }


def cmd_auth(args):
    # OpusClip's public API exposes no key-only status endpoint, so auth
    # either verifies against a known project or reports credential presence.
    if args.project_id:
        result = call("GET", f"/api/clip-projects/{args.project_id}", org_id=args.org_id)
        proj = result.get("project", result)
        print(json.dumps({"ok": True, "project": summarize_project(proj)}, indent=2))
    else:
        get_surrogate()  # raises with connect guidance if missing
        print(json.dumps({
            "ok": True,
            "note": "credential is stored; the key itself was not verified "
                    "(OpusClip has no key-only status endpoint). Pass "
                    "--project-id to verify against a real project.",
        }, indent=2))


def cmd_project_create(args):
    payload = {"videoUrl": args.video_url}
    if args.brand_template_id:
        payload["brandTemplateId"] = args.brand_template_id
    if args.genre:
        payload.setdefault("curationPref", {})["genre"] = args.genre
    if args.keywords:
        payload.setdefault("curationPref", {})["topicKeywords"] = [
            k.strip() for k in args.keywords.split(",")
        ]
    if args.webhook_url:
        payload["conclusionActions"] = [{"type": "WEBHOOK", "webhookUrl": args.webhook_url,
                                         "notifyFailure": True}]
    result = call("POST", "/api/clip-projects", payload, org_id=args.org_id)
    proj = result.get("project", result)
    print(json.dumps(summarize_project(proj), indent=2))


def cmd_project_get(args):
    result = call("GET", f"/api/clip-projects/{args.id}", org_id=args.org_id)
    proj = result.get("project", result)
    print(json.dumps(summarize_project(proj), indent=2))


def cmd_clips(args):
    result = call("GET", "/api/exportable-clips",
                  params={"q": "findByProjectId", "projectId": args.project_id},
                  org_id=args.org_id)
    clips = result if isinstance(result, list) else result.get("clips", result.get("data", []))
    print(json.dumps([summarize_clip(c) for c in clips], indent=2))


def cmd_upload_link(args):
    result = call("POST", "/api/upload-links", {"video": {"usecase": "LocalUpload"}},
                  org_id=args.org_id)
    print(json.dumps(result, indent=2))


def add_org(p):
    p.add_argument("--org-id", help="OpusClip org id (sent as x-opus-org-id)")


def main():
    parser = argparse.ArgumentParser(description="OpusClip API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="check connection (verifies against --project-id if given)")
    p.add_argument("--project-id", help="known project id to verify the key against")
    add_org(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("project-create", help="create a clip project from a video URL (confirm first: metered)")
    p.add_argument("--video-url", required=True, help="public video URL (e.g. YouTube)")
    p.add_argument("--brand-template-id", help="brand template id, e.g. preset-fancy-Karaoke")
    p.add_argument("--genre", help="curation genre, e.g. podcast")
    p.add_argument("--keywords", help="comma-separated topic keywords")
    p.add_argument("--webhook-url", help="webhook notified on completion")
    add_org(p)
    p.set_defaults(func=cmd_project_create)

    p = sub.add_parser("project-get", help="get a clip project's status")
    p.add_argument("--id", required=True, help="project id")
    add_org(p)
    p.set_defaults(func=cmd_project_get)

    p = sub.add_parser("clips", help="list exportable clips for a project (with virality scores when returned)")
    p.add_argument("--project-id", required=True)
    add_org(p)
    p.set_defaults(func=cmd_clips)

    p = sub.add_parser("upload-link", help="generate a resumable upload link for a local file")
    add_org(p)
    p.set_defaults(func=cmd_upload_link)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
