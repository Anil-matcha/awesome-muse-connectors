#!/usr/bin/env python3
"""Minimal Ashby API CLI for the muse-connectors ashby skill.

Auth (keyed endpoints): HTTP Basic with the API key as the username and a
blank password: `Authorization: Basic base64("<key>:")`, computed with
stdlib base64. Loads the per-user `custom.ashby` credential as a surrogate
via the bundled dynamic_credentials helper. The real key never touches this
script: the runtime swaps the surrogate on approved egress, only to
api.ashbyhq.com.

The API is RPC-style: every keyed call is a POST to a named endpoint.

Public job feed: `jobs-public` needs NO credential and the CLI skips the
credential load for it entirely, so it works without any API key.

Pipeline writes (application-create, application-move) are
confirmation-gated: they change a real hiring pipeline.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.ashby"
ALLOWED_HOSTS = ("api.ashbyhq.com",)
API = "https://api.ashbyhq.com"

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


def authed_call(path: str, payload: dict | None = None) -> dict:
    """POST to an RPC endpoint with Basic auth built from the surrogate."""
    url = API + path
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    data = json.dumps(payload if payload is not None else {}).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        surrogate = dynamic_credential_entry(CREDENTIAL_NAME)["surrogate"]
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    # Basic auth: key as username, blank password.
    token = base64.b64encode(f"{surrogate}:".encode("utf-8")).decode("ascii")
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", {}).get("message", str(exc)) \
                if isinstance(body.get("error"), dict) else str(exc)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: ashby returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def public_call(org: str) -> dict:
    """GET the credential-free public job feed. No credential is loaded."""
    url = f"{API}/posting-api/job-board/{urllib.parse.quote(org, safe='')}"
    ensure_allowed_url(url, allowed_hosts=ALLOWED_HOSTS)
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: ashby returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def unwrap(result: dict) -> object:
    # RPC responses carry the payload under "results" (or "result").
    if isinstance(result, dict):
        for key in ("results", "result"):
            if key in result:
                return result[key]
    return result


def load_json(text: str | None) -> dict:
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --json is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        sys.exit("error: --json must be a JSON object")
    return payload


def cmd_auth(_args):
    result = unwrap(authed_call("/job.list", {"limit": 1}))
    count = len(result) if isinstance(result, list) else 0
    print(json.dumps({"ok": True, "jobs": count}, indent=2))


def cmd_candidate_list(args):
    result = unwrap(authed_call("/candidate.list", load_json(args.json)))
    print(json.dumps(result, indent=2))


def cmd_job_list(args):
    result = unwrap(authed_call("/job.list", load_json(args.json)))
    print(json.dumps(result, indent=2))


def cmd_application_list(args):
    result = unwrap(authed_call("/application.list", load_json(args.json)))
    print(json.dumps(result, indent=2))


def cmd_application_create(args):
    result = unwrap(authed_call("/application.create", load_json(args.json)))
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_application_move(args):
    payload = load_json(args.json)
    if args.application_id:
        payload["applicationId"] = args.application_id
    if args.stage_id:
        payload["stageId"] = args.stage_id
    result = unwrap(authed_call("/application.updateStage", payload))
    print(json.dumps({"ok": True, "result": result}, indent=2))


def cmd_jobs_public(args):
    # No credential is loaded or sent for the public job feed.
    result = public_call(args.org)
    jobs = result.get("jobs", []) if isinstance(result, dict) else []
    out = [
        {"id": j.get("id"), "title": j.get("title"),
         "department": j.get("departmentName") or j.get("department"),
         "location": j.get("locationName") or j.get("location"),
         "employmentType": j.get("employmentType"),
         "publishedAt": j.get("publishedAt"),
         "jobUrl": j.get("jobUrl")}
        for j in (jobs if isinstance(jobs, list) else [])
    ]
    print(json.dumps(out, indent=2))


def add_json(p):
    p.add_argument("--json", default=None,
                   help="RPC request body as a JSON object string")


def main():
    parser = argparse.ArgumentParser(description="Ashby API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the API key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("candidate-list", help="list candidates")
    add_json(p)
    p.set_defaults(func=cmd_candidate_list)

    p = sub.add_parser("job-list", help="list jobs")
    add_json(p)
    p.set_defaults(func=cmd_job_list)

    p = sub.add_parser("application-list", help="list applications/pipeline")
    add_json(p)
    p.set_defaults(func=cmd_application_list)

    p = sub.add_parser("application-create",
                       help="create an application (confirm first)")
    add_json(p)
    p.set_defaults(func=cmd_application_create)

    p = sub.add_parser("application-move",
                       help="move an application between stages (confirm first)")
    add_json(p)
    p.add_argument("--application-id", default=None)
    p.add_argument("--stage-id", default=None)
    p.set_defaults(func=cmd_application_move)

    p = sub.add_parser("jobs-public",
                       help="list a company's public job board (no credential needed)")
    p.add_argument("--org", required=True,
                   help="organization host, e.g. the part after app.ashbyhq.com in their job-board URL")
    p.set_defaults(func=cmd_jobs_public)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
