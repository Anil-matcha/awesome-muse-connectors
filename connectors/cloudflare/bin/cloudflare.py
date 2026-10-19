#!/usr/bin/env python3
"""Cloudflare API operations using the stored custom.cloudflare credential.

Auth goes through the authd surrogate exchange via dynamic_credentials —
never prints or persists raw credentials. All output is JSON.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import (
    add_surrogate_to_request,
    read_json_response,
    DynamicCredentialError,
)

BASE = "https://api.cloudflare.com/client/v4"
ALLOWED = ["api.cloudflare.com"]
CRED = "custom.cloudflare"
# Fallback account id, used only when the token's scopes do not permit
# GET /accounts. Set it with the global --account-id option (an account id
# is configuration, not a credential). Never hardcode a real one here.
ACCOUNT_ID = None
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _request(method, path, body=None, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", UA)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(
        req, CRED, entry_name="access_token", allowed_hosts=ALLOWED
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = {"error": f"HTTP {e.code}"}
        return e.code, payload


def _request_jwt(path, jwt, body=None, params=None, method=None):
    """Same as _request but Bearer-authenticates with a Pages upload JWT."""
    import urllib.parse
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method or ("POST" if body is not None else "GET"))
    req.add_header("User-Agent", UA)
    req.add_header("Authorization", f"Bearer {jwt}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": f"HTTP {e.code}"}


def _require_confirm(args, effect):
    # Writes are confirmation-gated: the caller must pass --confirm naming
    # the exact effect, obtained from the user in conversation first.
    confirm = getattr(args, "confirm", None)
    if not confirm or len(confirm.strip()) < 3:
        print(json.dumps({"error": f"refused: write not confirmed. This would: {effect}. "
                                   f"Re-run with --confirm '<exact effect>' after the user confirms."}))
        raise SystemExit(3)


def _ok(status, payload):
    return status == 200 and isinstance(payload, dict) and payload.get("success")


def _account_id():
    status, payload = _request("GET", "/accounts")
    if _ok(status, payload) and payload["result"]:
        return payload["result"][0]["id"]
    return ACCOUNT_ID


def cmd_verify(args):
    # /user/tokens/verify 401s account-owned (cfat_) tokens BY DESIGN;
    # those must use /accounts/{id}/tokens/verify instead.
    if args.account_id:
        path = f"/accounts/{args.account_id}/tokens/verify"
    else:
        path = "/user/tokens/verify"
    status, payload = _request("GET", path)
    print(json.dumps({"http": status, "path": path,
                      "result": payload}, indent=2))


def cmd_accounts(_args):
    status, payload = _request("GET", "/accounts")
    print(json.dumps({"http": status, "result": payload}, indent=2))


def cmd_zones(args):
    params = {}
    if args.name:
        params["name"] = args.name
    status, payload = _request("GET", "/zones", params=params)
    print(json.dumps({"http": status, "result": payload}, indent=2))


def cmd_zone_add(args):
    _require_confirm(args, f"add zone {args.name} to the account")
    account_id = _account_id()
    if not account_id:
        print(json.dumps({"error": "could not determine account", "http": status}))
        return
    status, payload = _request("POST", "/zones", {
        "name": args.name,
        "account": {"id": account_id},
    })
    print(json.dumps({"http": status, "result": payload}, indent=2))


def _zone_id(name):
    status, payload = _request("GET", "/zones", params={"name": name})
    if _ok(status, payload) and payload["result"]:
        return payload["result"][0]["id"]
    return None


def cmd_dns_list(args):
    zid = _zone_id(args.zone)
    if not zid:
        print(json.dumps({"error": f"zone not found: {args.zone}"}))
        return
    status, payload = _request(
        "GET", f"/zones/{zid}/dns_records", params={"per_page": 100})
    print(json.dumps({"http": status, "result": payload}, indent=2))


def cmd_dns_add(args):
    _require_confirm(args, f"add {args.type} record {args.name} -> {args.content} in zone {args.zone}")
    zid = _zone_id(args.zone)
    if not zid:
        print(json.dumps({"error": f"zone not found: {args.zone}"}))
        return
    record = {"type": args.type, "name": args.name,
              "content": args.content, "ttl": args.ttl}
    if args.proxied:
        record["proxied"] = True
    if args.priority is not None:
        record["priority"] = args.priority
    status, payload = _request("POST", f"/zones/{zid}/dns_records", record)
    print(json.dumps({"http": status, "result": payload}, indent=2))


def cmd_pages_projects(args):
    account_id = _account_id()
    if not account_id:
        print(json.dumps({"error": "could not determine account"}))
        return
    status, payload = _request(
        "GET", f"/accounts/{account_id}/pages/projects")
    print(json.dumps({"http": status, "result": payload}, indent=2))


def cmd_pages_project_create(args):
    _require_confirm(args, f"create Pages project {args.name}")
    account_id = _account_id()
    if not account_id:
        print(json.dumps({"error": "could not determine account"}))
        return
    status, payload = _request(
        "POST", f"/accounts/{account_id}/pages/projects",
        {"name": args.name, "production_branch": "main"})
    print(json.dumps({"http": status, "result": payload}, indent=2))


def _pages_account_id():
    return _account_id()


def _pages_hash(data, rel):
    """Wrangler-compatible asset hash: blake3(base64(content) + ext)[:32]."""
    import base64
    try:
        from blake3 import blake3
    except ImportError:
        raise SystemExit("pages-deploy needs the blake3 package (pip install blake3) "
                         "for Wrangler-compatible asset hashes")
    ext = rel.rsplit(".", 1)[-1] if "." in rel.rsplit("/", 1)[-1] else ""
    b64 = base64.b64encode(data).decode()
    return blake3((b64 + ext).encode()).hexdigest()[:32]


def _content_type(path):
    if path.endswith(".html"):
        return "text/html"
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".css"):
        return "text/css"
    if path.endswith(".js"):
        return "application/javascript"
    if path.endswith((".png",)):
        return "image/png"
    return "application/octet-stream"


def _multipart(fields):
    import uuid
    boundary = uuid.uuid4().hex
    lines = []
    for name, value, filename, ctype in fields:
        lines.append(f"--{boundary}")
        if filename:
            lines.append(
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"')
            lines.append(f"Content-Type: {ctype}")
        else:
            lines.append(f'Content-Disposition: form-data; name="{name}"')
        lines.append("")
        lines.append(value)
    lines.append(f"--{boundary}--")
    lines.append("")
    body = "\r\n".join(lines).encode()
    return body, f"multipart/form-data; boundary={boundary}"


def cmd_pages_deploy(args):
    _require_confirm(args, f"deploy {args.dir} to Pages project {args.project} (becomes production immediately)")
    """Direct-upload deploy of a local directory to a Pages project.
    Mirrors wrangler pages deploy: assets -> check-missing/upload/upsert,
    then multipart deployment create with manifest."""
    import base64
    account_id = _pages_account_id()
    root = os.path.abspath(args.dir)
    files = []  # (rel, hash, size, data)
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = "/" + os.path.relpath(full, root).replace(os.sep, "/")
            with open(full, "rb") as f:
                data = f.read()
            files.append((rel, _pages_hash(data, rel), len(data), data))
    hashes = [h for _, h, _, _ in files]

    # 0. fetch the short-lived upload JWT (asset endpoints take the JWT,
    #    not the API token)
    status, payload = _request(
        "GET",
        f"/accounts/{account_id}/pages/projects/{args.project}/upload-token")
    if status != 200 or not payload.get("success"):
        print(json.dumps({"error": "upload-token failed", "http": status,
                          "result": payload}, indent=2))
        return
    jwt = payload["result"]["jwt"]

    # 1. which assets are missing?
    status, payload = _request_jwt(
        "/pages/assets/check-missing", jwt, {"hashes": hashes})
    if status != 200 or not payload.get("success"):
        print(json.dumps({"error": "check-missing failed", "http": status,
                          "result": payload}, indent=2))
        return
    missing = set(payload["result"] or [])

    # 2. upload missing assets (base64 payload like wrangler)
    if missing:
        up = []
        for rel, h, _size, data in files:
            if h in missing:
                up.append({
                    "key": h,
                    "value": base64.b64encode(data).decode(),
                    "metadata": {"contentType": _content_type(rel)},
                    "base64": True,
                })
        status, payload = _request_jwt("/pages/assets/upload", jwt, up)
        if status != 200 or not payload.get("success"):
            print(json.dumps({"error": "asset upload failed", "http": status,
                              "result": payload}, indent=2))
            return

    # 3. confirm hashes
    status, payload = _request_jwt(
        "/pages/assets/upsert-hashes", jwt, {"hashes": hashes})
    if status != 200 or not payload.get("success"):
        print(json.dumps({"error": "upsert-hashes failed", "http": status,
                          "result": payload}, indent=2))
        return

    # 4. create deployment with multipart manifest
    manifest = {rel: h for rel, h, _, _ in files}
    body, ctype = _multipart([("manifest", json.dumps(manifest), None, None)])
    url = (BASE + f"/accounts/{account_id}/pages/projects/"
           f"{args.project}/deployments")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("User-Agent", UA)
    req.add_header("Content-Type", ctype)
    add_surrogate_to_request(
        req, CRED, entry_name="access_token", allowed_hosts=ALLOWED)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            payload = read_json_response(resp)
            status = resp.status
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = {"error": f"HTTP {e.code}"}
        status = e.code
    if status == 200 and payload.get("success"):
        res = payload["result"]
        print(json.dumps({"deployment": res.get("id"), "url": res.get("url"),
                          "environment": res.get("environment")}, indent=2))
    else:
        print(json.dumps({"error": "deployment create failed",
                          "http": status, "result": payload}, indent=2))


def cmd_workers_kv_create(args):
    _require_confirm(args, f"create Workers KV namespace {args.title}")
    account_id = _account_id()
    if not account_id:
        print(json.dumps({"error": "could not determine account"}))
        return
    status, payload = _request(
        "POST", f"/accounts/{account_id}/storage/kv/namespaces",
        {"title": args.title})
    print(json.dumps({"http": status, "result": payload}, indent=2))


def _workers_multipart(metadata, script_text):
    import uuid
    boundary = uuid.uuid4().hex
    # For ES-module workers the file part NAME must equal metadata.main_module.
    mod = metadata.get("main_module", "worker.js")
    parts = []
    parts.append(f"--{boundary}\r\n"
                 'Content-Disposition: form-data; name="metadata"\r\n'
                 "Content-Type: application/json\r\n\r\n"
                 + json.dumps(metadata) + "\r\n")
    parts.append(f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="{mod}"; filename="{mod}"\r\n'
                 "Content-Type: application/javascript+module\r\n\r\n"
                 + script_text + "\r\n")
    parts.append(f"--{boundary}--\r\n")
    return "".join(parts).encode(), f"multipart/form-data; boundary={boundary}"


def cmd_workers_deploy(args):
    _require_confirm(args, f"deploy Worker script {args.name} from {args.file}")
    account_id = _account_id()
    if not account_id:
        print(json.dumps({"error": "could not determine account"}))
        return
    with open(args.file) as f:
        script_text = f.read()
    bindings = []
    for kv in args.kv or []:
        name, nsid = kv.split(":", 1)
        bindings.append({"type": "kv_namespace", "name": name,
                         "namespace_id": nsid})
    metadata = {"main_module": "worker.js", "bindings": bindings,
                "compatibility_date": "2024-01-01", "type": "module"}
    body, ctype = _workers_multipart(metadata, script_text)
    url = BASE + f"/accounts/{account_id}/workers/scripts/{args.name}"
    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("User-Agent", UA)
    req.add_header("Content-Type", ctype)
    add_surrogate_to_request(
        req, CRED, entry_name="access_token", allowed_hosts=ALLOWED)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = read_json_response(resp)
            status = resp.status
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = {"error": f"HTTP {e.code}"}
        status = e.code
    print(json.dumps({"http": status, "result": payload}, indent=2))


def cmd_workers_secret_put(args):
    _require_confirm(args, f"set secret {args.key} on Worker {args.script}")
    account_id = _account_id()
    if not account_id:
        print(json.dumps({"error": "could not determine account"}))
        return
    with open(args.from_file) as f:
        value = f.read().strip()
    status, payload = _request(
        "PUT",
        f"/accounts/{account_id}/workers/scripts/{args.script}/secrets",
        {"name": args.key, "text": value, "type": "secret_text"})
    print(json.dumps({"http": status, "result": payload}, indent=2))


def cmd_workers_route_add(args):
    _require_confirm(args, f"add Worker route {args.pattern} -> {args.script} in zone {args.zone}")
    zid = _zone_id(args.zone)
    if not zid:
        print(json.dumps({"error": f"zone not found: {args.zone}"}))
        return
    status, payload = _request(
        "POST", f"/zones/{zid}/workers/routes",
        {"pattern": args.pattern, "script": args.script})
    print(json.dumps({"http": status, "result": payload}, indent=2))


def main():
    ap = argparse.ArgumentParser(prog="cf.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("verify")
    pv.add_argument("--account-id", default=None)
    pv.set_defaults(fn=cmd_verify)
    pa = sub.add_parser("auth")  # status check alias
    pa.add_argument("--account-id", default=None)
    pa.set_defaults(fn=cmd_verify)
    sub.add_parser("accounts").set_defaults(fn=cmd_accounts)

    p = sub.add_parser("zones")
    p.add_argument("--name")
    p.set_defaults(fn=cmd_zones)

    p = sub.add_parser("zone-add")
    p.add_argument("name")
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")
    p.add_argument("--account-id", default=None, help="account id fallback when the token cannot list accounts")
    p.set_defaults(fn=cmd_zone_add)

    p = sub.add_parser("dns-list")
    p.add_argument("zone")
    p.set_defaults(fn=cmd_dns_list)

    p = sub.add_parser("dns-add")
    p.add_argument("zone")
    p.add_argument("--type", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--content", required=True)
    p.add_argument("--ttl", type=int, default=3600)
    p.add_argument("--proxied", action="store_true")
    p.add_argument("--priority", type=int, default=None)
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")
    p.set_defaults(fn=cmd_dns_add)

    p = sub.add_parser("pages-projects")
    p.add_argument("--account-id", default=None, help="account id fallback when the token cannot list accounts")
    p.set_defaults(fn=cmd_pages_projects)

    p = sub.add_parser("pages-project-create")
    p.add_argument("name")
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")
    p.add_argument("--account-id", default=None, help="account id fallback when the token cannot list accounts")
    p.set_defaults(fn=cmd_pages_project_create)

    p = sub.add_parser("pages-deploy")
    p.add_argument("project")
    p.add_argument("--dir", required=True)
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")
    p.add_argument("--account-id", default=None, help="account id fallback when the token cannot list accounts")
    p.set_defaults(fn=cmd_pages_deploy)

    p = sub.add_parser("workers-kv-create")
    p.add_argument("title")
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")
    p.add_argument("--account-id", default=None, help="account id fallback when the token cannot list accounts")
    p.set_defaults(fn=cmd_workers_kv_create)

    p = sub.add_parser("workers-deploy")
    p.add_argument("name")
    p.add_argument("--file", required=True)
    p.add_argument("--kv", action="append", default=[],
                   help="KV binding as NAME:NAMESPACE_ID (repeatable)")
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")
    p.add_argument("--account-id", default=None, help="account id fallback when the token cannot list accounts")
    p.set_defaults(fn=cmd_workers_deploy)

    p = sub.add_parser("workers-secret-put")
    p.add_argument("script")
    p.add_argument("key")
    p.add_argument("--from-file", required=True)
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")
    p.add_argument("--account-id", default=None, help="account id fallback when the token cannot list accounts")
    p.set_defaults(fn=cmd_workers_secret_put)

    p = sub.add_parser("workers-route-add")
    p.add_argument("zone")
    p.add_argument("--pattern", required=True)
    p.add_argument("--script", required=True)
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")
    p.set_defaults(fn=cmd_workers_route_add)

    args = ap.parse_args()
    if getattr(args, "account_id", None):
        global ACCOUNT_ID
        ACCOUNT_ID = args.account_id
    try:
        args.fn(args)
    except DynamicCredentialError as e:
        print(json.dumps({"error": f"credential problem: {e}"}))


if __name__ == "__main__":
    main()
