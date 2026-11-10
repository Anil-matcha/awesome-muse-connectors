#!/usr/bin/env python3
"""OneDrive file operations via Microsoft Graph, using the stored
custom.onedrive credential (OAuth2, delegated).

Never prints or persists raw credentials; auth goes through the authd
surrogate exchange via dynamic_credentials.add_surrogate_to_request.
"""
import argparse
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
    read_response_body,
    DynamicCredentialError,
)

BASE = "https://graph.microsoft.com/v1.0"
ALLOWED = ["graph.microsoft.com"]
CRED = "custom.onedrive"


def _request(method, path, body=None, raw=False):
    url = BASE + path
    data = None
    if body is not None:
        if isinstance(body, (bytes, bytearray)):
            data = bytes(body)
        else:
            data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    if isinstance(body, dict):
        req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(
        req, CRED, entry_name="access_token", allowed_hosts=ALLOWED
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            if raw:
                return resp.status, read_response_body(resp)
            return resp.status, read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = {"error": f"HTTP {e.code}"}
        return e.code, payload


def _item_path(remote):
    remote = (remote or "").strip().strip("/")
    if not remote:
        return "/me/drive/root"
    segments = [urllib.parse.quote(seg) for seg in remote.split("/")]
    return "/me/drive/root:/" + "/".join(segments)


def cmd_me(_args):
    status, payload = _request("GET", "/me?$select=displayName,mail,userPrincipalName")
    print(json.dumps({"status": status, "me": payload}, indent=2)[:2000])


def cmd_ls(args):
    path = _item_path(args.remote) + ":/children"
    if not args.remote:
        path = "/me/drive/root/children"
    params = {"$top": str(args.limit), "$select": "name,size,folder,file,lastModifiedDateTime"}
    path += "?" + urllib.parse.urlencode(params)
    status, payload = _request("GET", path)
    if status != 200:
        print(json.dumps({"status": status, "error": payload}, indent=2)[:2000])
        return
    items = []
    for it in payload.get("value", []):
        kind = "folder" if "folder" in it else "file"
        items.append({"name": it.get("name"), "type": kind, "size": it.get("size")})
    print(json.dumps({"status": status, "path": args.remote or "/", "items": items}, indent=2)[:6000])


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _download_bytes(remote):
    """Follow Graph's 302 to the pre-authenticated download URL (tempauth).
    The tempauth URL carries its own auth — never attach our bearer to it,
    and never log or persist the full URL (it is a bearer credential)."""
    url = BASE + _item_path(remote) + ":/content"
    req = urllib.request.Request(url, method="GET")
    req.add_header(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    add_surrogate_to_request(
        req, CRED, entry_name="access_token", allowed_hosts=ALLOWED
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=120) as resp:
            # 200 with no redirect (small files sometimes inline) — unlikely, but handle it.
            return resp.status, read_response_body(resp)
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            try:
                payload = json.loads(e.read().decode())
            except Exception:
                payload = {"error": f"HTTP {e.code}"}
            return e.code, payload
        location = e.headers.get("Location", "")
    if not location:
        return 502, {"error": "no download redirect from Graph"}
    dl = urllib.request.Request(location, method="GET")
    dl.add_header(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    try:
        with urllib.request.urlopen(dl, timeout=300) as resp:
            return resp.status, read_response_body(resp)
    except urllib.error.HTTPError as e:
        return e.code, {"error": f"download HTTP {e.code}"}


def cmd_download(args):
    status, data = _download_bytes(args.remote)
    if status != 200:
        try:
            err = json.loads(data.decode()) if isinstance(data, (bytes, bytearray)) else data
        except Exception:
            err = {"error": f"HTTP {status}"}
        print(json.dumps({"status": status, "error": err}, indent=2)[:2000])
        sys.exit(1)
    os.makedirs(os.path.dirname(os.path.abspath(args.local)) or ".", exist_ok=True)
    with open(args.local, "wb") as f:
        f.write(data)
    print(json.dumps({"status": status, "saved": args.local, "bytes": len(data)}))


def cmd_upload(args):
    _require_confirm(args, f"upload {args.local} to OneDrive path {args.remote}")
    if not os.path.isfile(args.local):
        print(json.dumps({"error": f"local file not found: {args.local}"}))
        sys.exit(1)
    with open(args.local, "rb") as f:
        content = f.read()
    status, payload = _request("PUT", _item_path(args.remote) + ":/content", body=content)
    if status in (200, 201):
        print(json.dumps({"status": status, "name": payload.get("name"), "size": payload.get("size")}))
    else:
        print(json.dumps({"status": status, "error": payload}, indent=2)[:2000])
        sys.exit(1)


def cmd_mkdir(args):
    _require_confirm(args, f"create OneDrive folder {args.remote}")
    parent, _, name = (args.remote.strip().strip("/")).rpartition("/")
    parent_path = _item_path(parent) + ":/children"
    if not parent:
        parent_path = "/me/drive/root/children"
    body = {"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
    status, payload = _request("POST", parent_path, body=body)
    if status in (200, 201):
        print(json.dumps({"status": status, "name": payload.get("name")}))
    else:
        print(json.dumps({"status": status, "error": payload}, indent=2)[:2000])
        sys.exit(1)


def cmd_search(args):
    q = urllib.parse.quote(args.query)
    path = f"/me/drive/root/search(q='{q}')?$top={args.limit}&$select=name,size,folder,file,parentReference"
    status, payload = _request("GET", path)
    if status != 200:
        print(json.dumps({"status": status, "error": payload}, indent=2)[:2000])
        return
    items = []
    for it in payload.get("value", []):
        kind = "folder" if "folder" in it else "file"
        parent = (it.get("parentReference") or {}).get("path", "")
        items.append({"name": it.get("name"), "type": kind, "parent": parent})
    print(json.dumps({"status": status, "items": items}, indent=2)[:6000])


def _guard_vault(remote):
    # Personal Vault is always off-limits, no exceptions.
    if "personal vault" in (remote or "").lower():
        print(json.dumps({"error": "refused: Personal Vault is always off-limits"}))
        sys.exit(3)


def _require_confirm(args, effect):
    # Writes are confirmation-gated: the caller must pass --confirm naming
    # the exact effect, obtained from the user in conversation first.
    confirm = getattr(args, "confirm", None)
    if not confirm or len(confirm.strip()) < 3:
        print(json.dumps({"error": f"refused: write not confirmed. This would: {effect}. "
                                   f"Re-run with --confirm \"<exact effect>\" after the user confirms."}))
        sys.exit(3)


def cmd_rename(args):
    _require_confirm(args, f"rename OneDrive {args.remote} to {args.new_name}")
    _guard_vault(args.remote)
    status, payload = _request("PATCH", _item_path(args.remote), body={"name": args.new_name})
    if status == 200:
        print(json.dumps({"status": status, "name": payload.get("name")}))
    else:
        print(json.dumps({"status": status, "error": payload}, indent=2)[:2000])
        sys.exit(1)


def cmd_move(args):
    _require_confirm(args, f"move OneDrive {args.remote} to folder {args.dest}")
    _guard_vault(args.remote)
    _guard_vault(args.dest)
    dest = args.dest.strip().strip("/")
    body = {"parentReference": {"path": "/drive/root:/" + dest if dest else "/drive/root"}}
    status, payload = _request("PATCH", _item_path(args.remote), body=body)
    if status == 200:
        parent = (payload.get("parentReference") or {}).get("path", "")
        print(json.dumps({"status": status, "name": payload.get("name"), "parent": parent}))
    else:
        print(json.dumps({"status": status, "error": payload}, indent=2)[:2000])
        sys.exit(1)


def cmd_recycle(args):
    # DELETE on OneDrive consumer moves the item to the recycle bin (recoverable).
    # Never empty the recycle bin from this CLI.
    # Note: Graph answers 204 with an empty body, so read raw and don't parse JSON.
    _require_confirm(args, f"move OneDrive {args.remote} to the recycle bin")
    _guard_vault(args.remote)
    status, data = _request("DELETE", _item_path(args.remote), raw=True)
    if status in (200, 202, 204):
        print(json.dumps({"status": status, "recycled": args.remote}))
    else:
        try:
            err = json.loads(data.decode())
        except Exception:
            err = {"error": f"HTTP {status}"}
        print(json.dumps({"status": status, "error": err}, indent=2)[:2000])
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(prog="onedrive", description="OneDrive via Microsoft Graph")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("me", help="Verify auth and show the signed-in user")

    p = sub.add_parser("ls", help="List a OneDrive folder")
    p.add_argument("remote", nargs="?", default="", help="Folder path in OneDrive (default: root)")
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("download", help="Download a file from OneDrive")
    p.add_argument("remote", help="File path in OneDrive")
    p.add_argument("local", help="Local destination path")

    p = sub.add_parser("upload", help="Upload a local file to OneDrive")
    p.add_argument("local", help="Local source path")
    p.add_argument("remote", help="Destination path in OneDrive")
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")

    p = sub.add_parser("mkdir", help="Create a folder in OneDrive")
    p.add_argument("remote", help="New folder path in OneDrive")
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")

    p = sub.add_parser("search", help="Search OneDrive")
    p.add_argument("query", help="Search text")
    p.add_argument("--limit", type=int, default=25)

    p = sub.add_parser("rename", help="Rename a file or folder in OneDrive")
    p.add_argument("remote", help="Current path in OneDrive")
    p.add_argument("new_name", help="New name (not a path)")
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")

    p = sub.add_parser("move", help="Move a file or folder to another OneDrive folder")
    p.add_argument("remote", help="Current path in OneDrive")
    p.add_argument("dest", help="Destination folder path in OneDrive")
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")

    p = sub.add_parser("recycle", help="Move a file or folder to the OneDrive recycle bin (recoverable)")
    p.add_argument("remote", help="Path in OneDrive")
    p.add_argument("--confirm", help="REQUIRED for writes: the exact effect, confirmed by the user")

    args = ap.parse_args()
    try:
        {"me": cmd_me, "ls": cmd_ls, "download": cmd_download,
         "upload": cmd_upload, "mkdir": cmd_mkdir, "search": cmd_search,
         "rename": cmd_rename, "move": cmd_move, "recycle": cmd_recycle}[args.cmd](args)
    except DynamicCredentialError as e:
        print(json.dumps({"error": f"credential problem: {e}"}))
        sys.exit(2)


if __name__ == "__main__":
    main()
