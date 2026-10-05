#!/usr/bin/env python3
"""Cohesivity infrastructure CLI for the muse-connectors skill."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

BASE_URL = "https://cohesivity.ai"

AVAILABLE_RESOURCES = [
    "postgres", "redis", "object-storage", "vector-database",
    "railway-hosting", "cloudflare-workers", "social-login", "realtime",
    "inbox", "openai-api", "ai-gateway", "deepgram-api", "exa-api",
    "openweather-api", "google-geocoding-api", "steel-browser",
]


def read_cohesivity_file(project_dir: str) -> dict:
    path = os.path.join(project_dir, ".cohesivity")
    if not os.path.isfile(path):
        return {}
    result = {}
    with open(path, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip()
    return result


def get_management_key(project_dir: str) -> str:
    creds = read_cohesivity_file(project_dir)
    key = creds.get("coh_management_key", "")
    if key:
        return key
    try:
        sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
        from dynamic_credentials import get_credential
        return get_credential("custom.cohesivity")
    except Exception:
        pass
    sys.exit(
        f"error: no .cohesivity found in {os.path.abspath(project_dir)}\n"
        "Run: bin/cohesivity.py init --confirm \"create ephemeral tenant\""
    )


def api_call(method, path, management_key=None, payload=None):
    url = BASE_URL + path
    headers = {"User-Agent": "cohesivity-muse-connector/1.0"}
    if management_key:
        headers["Authorization"] = f"Bearer {management_key}"
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:1000]
        try:
            msg = json.loads(body).get("error", body)
        except Exception:
            msg = body
        sys.exit(f"error: HTTP {exc.code}: {msg}")
    except Exception as exc:
        sys.exit(f"error: request failed: {exc}")


def need_confirm(args, expected, effect):
    if getattr(args, "confirm", None) == expected:
        return
    sys.exit(f"refusing: {effect}\n  --confirm \"{expected}\"")


def cmd_init(args):
    project_dir = args.project_dir
    coh_path = os.path.join(project_dir, ".cohesivity")
    if os.path.isfile(coh_path):
        sys.exit(f"error: {coh_path} already exists. Reuse the existing tenant.")
    need_confirm(args, "create ephemeral tenant",
                 "creating a new 72-hour ephemeral Cohesivity tenant")
    npx = subprocess.run(["which", "npx"], capture_output=True).returncode == 0
    if npx:
        cmd = ["npx", "@cohesivity/init",
               "--attribution", "gh-awesome-muse-connectors"]
    elif subprocess.run(["which", "curl"], capture_output=True).returncode == 0:
        cmd = ["bash", "-c",
               "curl -fsSL https://cohesivity.ai/quickstart.sh | bash"
               " -s -- --attribution gh-awesome-muse-connectors"]
    else:
        sys.exit("error: npx or curl required to create a tenant")
    subprocess.run(cmd, cwd=project_dir)
    if not os.path.isfile(coh_path):
        sys.exit("error: quickstart did not create .cohesivity")
    creds = read_cohesivity_file(project_dir)
    print(json.dumps({
        "ok": True,
        "tenant_id": creds.get("tenant_id"),
        "expires_at": creds.get("expires_at"),
        "lifecycle": creds.get("tenant_lifecycle", "ephemeral"),
    }, indent=2))


def cmd_auth(args):
    key = get_management_key(args.project_dir)
    data = api_call("GET", "/api/status", management_key=key)
    account = data.get("account", data)
    print(json.dumps({
        "ok": True,
        "tenant_id": account.get("tenant_id", data.get("tenant_id")),
        "lifecycle": account.get("tenant_lifecycle",
                                 data.get("tenant_lifecycle")),
        "runtime_profile": account.get("runtime_profile",
                                       data.get("runtime_profile")),
    }, indent=2))


def cmd_status(args):
    key = get_management_key(args.project_dir)
    data = api_call("GET", "/api/status", management_key=key)
    print(json.dumps(data, indent=2))


def cmd_resources(_args):
    print(json.dumps(AVAILABLE_RESOURCES, indent=2))


def cmd_provision(args):
    key = get_management_key(args.project_dir)
    if args.resource:
        names = [args.resource]
    elif args.resources:
        names = [r.strip() for r in args.resources.split(",") if r.strip()]
    else:
        sys.exit("error: provide --resource or --resources")
    for name in names:
        if name not in AVAILABLE_RESOURCES:
            sys.exit(f"error: unknown resource {name!r}. "
                     f"Available: {', '.join(AVAILABLE_RESOURCES)}")
    label = ", ".join(names)
    need_confirm(args, f"provision {label}", f"provisioning: {label}")
    if len(names) == 1:
        data = api_call("POST", f"/api/resources/{names[0]}",
                        management_key=key)
    else:
        data = api_call("POST", "/api/resources", management_key=key,
                        payload={"resources": names})
    print(json.dumps({"ok": True, "provisioned": names, "response": data},
                      indent=2))


def cmd_claim(args):
    key = get_management_key(args.project_dir)
    need_confirm(args, "generate claim link",
                 "generating a claim URL for the human")
    data = api_call("POST", "/api/claim/url", management_key=key)
    print(json.dumps({
        "ok": True,
        "approval_url": data.get("approval_url", ""),
        "instructions": "Share this URL with the human. "
                        "The management key stays agent-side.",
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Cohesivity infrastructure CLI (muse-connectors)")
    parser.add_argument("--project-dir", default=".",
                        help="directory containing .cohesivity")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create an ephemeral tenant")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("auth", help="verify the management key")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("status", help="tenant status and resources")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("resources", help="list available resource names")
    p.set_defaults(func=cmd_resources)

    p = sub.add_parser("provision", help="provision resources")
    p.add_argument("--resource", help="single resource name")
    p.add_argument("--resources", help="comma-separated resource names")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_provision)

    p = sub.add_parser("claim", help="generate claim URL for the human")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_claim)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
