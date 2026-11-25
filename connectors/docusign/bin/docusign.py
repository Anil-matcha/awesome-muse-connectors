#!/usr/bin/env python3
"""DocuSign eSignature REST API v2.1 CLI for the muse-connectors docusign
skill.

Auth: OAuth 2.0 Authorization Code Grant. The user approves access through
the secure credential flow (credentials.request_api_access) and the runtime
hands this script a fresh Bearer token via the bundled dynamic_credentials
helper. The real token never touches this script: the runtime swaps the
surrogate on approved egress, only to demo.docusign.net, docusign.net, or
account.docusign.com.

Scopes requested at approval: signature, extended.
HONESTY NOTE: this scope list and the endpoint paths below are taken from
DocuSign's public eSignature REST API v2.1 docs and have not been verified
in a live flow. In particular the account-discovery flow via
account.docusign.com/oauth/userinfo is provisional; if it fails, pass
--account-id and the correct --env explicitly.

Safety: the CLI defaults to the DEMO environment (demo.docusign.net), which
sends no legally effective documents. Switch to production only with
--env prod. Creating a DRAFT envelope is MEDIUM (needs --confirm every
call); SENDING an envelope is HIGH (needs an exact --confirm naming the
legal effect on every call).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.docusign"
ALLOWED_HOSTS = ("demo.docusign.net", "docusign.net", "account.docusign.com")
USERINFO_URL = "https://account.docusign.com/oauth/userinfo"
CONNECT_GUIDANCE = (
    "not connected: approve DocuSign access via the secure credential flow "
    "(credentials.request_api_access) as `custom.docusign` (OAuth "
    "Authorization Code Grant, scopes signature and extended; the "
    "integration key must be registered in the DocuSign Apps and Keys "
    "page), then retry."
)

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


def _request(url: str, method: str, payload: dict | None = None) -> bytes:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME,
                                 allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        if "missing" in str(exc) or "surrogate" in str(exc):
            sys.exit(CONNECT_GUIDANCE)
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("message", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: docusign returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def call_json(url: str, method: str, payload: dict | None = None) -> dict:
    raw = _request(url, method, payload)
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        sys.exit("error: docusign returned a non-JSON response")


def resolve_account(env: str, account_id: str | None) -> tuple[str, str]:
    """Discover base URI + account id from /oauth/userinfo.

    Returns (base_restapi_url, account_id).
    """
    user = call_json(USERINFO_URL, "GET")
    accounts = user.get("accounts", [])
    if not accounts:
        sys.exit("error: /oauth/userinfo returned no accounts")
    chosen = None
    if account_id:
        for a in accounts:
            if a.get("account_id") == account_id:
                chosen = a
                break
        if chosen is None:
            sys.exit(f"error: account {account_id} not in userinfo accounts")
    else:
        defaults = [a for a in accounts if a.get("is_default")]
        chosen = defaults[0] if defaults else accounts[0]
    base_uri = chosen.get("base_uri", "").rstrip("/")
    if not base_uri:
        sys.exit("error: account has no base_uri in userinfo")
    if env == "demo" and "demo" not in base_uri:
        sys.exit("error: --env demo but the account base_uri is not a demo "
                 f"host ({base_uri}); pass --env prod if you mean production")
    if env == "prod" and "demo" in base_uri:
        sys.exit("error: --env prod but the account base_uri is a demo host "
                 f"({base_uri})")
    return f"{base_uri}/restapi/v2.1", chosen.get("account_id")


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def load_file(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        sys.exit(f"error: could not read JSON file {path}: {exc}")


def cmd_auth(args):
    user = call_json(USERINFO_URL, "GET")
    accts = [{"account_id": a.get("account_id"),
              "account_name": a.get("account_name"),
              "is_default": a.get("is_default"),
              "base_uri": a.get("base_uri")}
             for a in user.get("accounts", [])]
    print(json.dumps({"ok": True, "sub": user.get("sub"),
                      "email": user.get("email"), "accounts": accts},
                     indent=2))


def cmd_envelopes(args):
    base, acct = resolve_account(args.env, args.account_id)
    query = f"from_date={args.from_date}&status={args.status}" if args.from_date else f"status={args.status}"
    result = call_json(f"{base}/accounts/{acct}/envelopes?{query}", "GET")
    items = [{"envelope_id": e.get("envelopeId"),
              "status": e.get("status"),
              "subject": e.get("emailSubject"),
              "sent": e.get("sentDateTime"),
              "changed": e.get("statusChangedDateTime")}
             for e in result.get("envelopes", [])]
    print(json.dumps(items, indent=2))


def cmd_envelope_get(args):
    base, acct = resolve_account(args.env, args.account_id)
    result = call_json(f"{base}/accounts/{acct}/envelopes/{args.envelope_id}",
                       "GET")
    recips = []
    for r in (result.get("recipients") or {}).get("signers", []):
        recips.append({"name": r.get("name"), "email": r.get("email"),
                       "status": r.get("status")})
    print(json.dumps({"envelope_id": result.get("envelopeId"),
                      "status": result.get("status"),
                      "subject": result.get("emailSubject"),
                      "sent": result.get("sentDateTime"),
                      "recipients": recips}, indent=2))


def cmd_envelope_create(args):
    base, acct = resolve_account(args.env, args.account_id)
    payload = load_file(args.file)
    payload["status"] = "created"  # DRAFT only, never sends
    expected = f"create DRAFT envelope from {args.file}"
    need_confirm(
        args, expected,
        "creating a DRAFT envelope only: no signer is notified and nothing "
        "becomes legally effective until it is sent.")
    result = call_json(f"{base}/accounts/{acct}/envelopes", "POST", payload)
    print(json.dumps({"ok": True,
                      "envelope_id": result.get("envelopeId"),
                      "status": result.get("status"),
                      "note": "draft created; NOT sent to signers"}, indent=2))


def cmd_envelope_send(args):
    base, acct = resolve_account(args.env, args.account_id)
    expected = (f"send envelope {args.envelope_id} to signers "
                "(legally binding signature request)")
    need_confirm(
        args, expected,
        "SENDING AN ENVELOPE TO SIGNERS CREATES A LEGALLY BINDING "
        "SIGNATURE REQUEST: signers are notified and the completed "
        "document is legally enforceable. This is irreversible in "
        "practice.")
    result = call_json(
        f"{base}/accounts/{acct}/envelopes/{args.envelope_id}",
        "POST", {"status": "sent"})
    print(json.dumps({"ok": True,
                      "envelope_id": result.get("envelopeId"),
                      "status": result.get("status"),
                      "env": args.env}, indent=2))


def cmd_envelope_status(args):
    base, acct = resolve_account(args.env, args.account_id)
    result = call_json(
        f"{base}/accounts/{acct}/envelopes/{args.envelope_id}?include=recipients",
        "GET")
    recips = []
    for r in (result.get("recipients") or {}).get("signers", []):
        recips.append({"name": r.get("name"), "email": r.get("email"),
                       "status": r.get("status"),
                       "delivered": r.get("deliveredDateTime"),
                       "signed": r.get("signedDateTime")})
    print(json.dumps({"envelope_id": result.get("envelopeId"),
                      "status": result.get("status"),
                      "recipients": recips}, indent=2))


def cmd_document_download(args):
    base, acct = resolve_account(args.env, args.account_id)
    raw = _request(
        f"{base}/accounts/{acct}/envelopes/{args.envelope_id}"
        f"/documents/{args.document_id}", "GET")
    try:
        with open(args.out, "wb") as fh:
            fh.write(raw)
    except OSError as exc:
        sys.exit(f"error: could not write {args.out}: {exc}")
    print(json.dumps({"ok": True, "envelope_id": args.envelope_id,
                      "document_id": args.document_id,
                      "bytes": len(raw), "saved_to": args.out}, indent=2))


def add_common(p):
    p.add_argument("--env", default="demo", choices=("demo", "prod"),
                   help="demo (default, no legal effect) or prod")
    p.add_argument("--account-id", default=None,
                   help="DocuSign account id (defaults to the default "
                        "account from /oauth/userinfo)")


def main():
    parser = argparse.ArgumentParser(
        description="DocuSign eSignature REST API v2.1 CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify OAuth; list accounts")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("envelopes", help="list envelopes")
    add_common(p)
    p.add_argument("--from-date", default=None,
                   help="ISO date, e.g. 2026-09-01")
    p.add_argument("--status", default="any",
                   choices=("any", "created", "sent", "delivered",
                            "signed", "completed", "declined", "voided"))
    p.set_defaults(func=cmd_envelopes)

    p = sub.add_parser("envelope-get", help="fetch an envelope")
    add_common(p)
    p.add_argument("--envelope-id", required=True)
    p.set_defaults(func=cmd_envelope_get)

    p = sub.add_parser("envelope-create",
                       help="create a DRAFT envelope (needs --confirm)")
    add_common(p)
    p.add_argument("--file", required=True,
                   help="JSON file with the envelope definition")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_envelope_create)

    p = sub.add_parser("envelope-send",
                       help="send a draft envelope (HIGH, legal effect)")
    add_common(p)
    p.add_argument("--envelope-id", required=True)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_envelope_send)

    p = sub.add_parser("envelope-status", help="envelope + recipient status")
    add_common(p)
    p.add_argument("--envelope-id", required=True)
    p.set_defaults(func=cmd_envelope_status)

    p = sub.add_parser("document-download",
                       help="download an envelope document to a file")
    add_common(p)
    p.add_argument("--envelope-id", required=True)
    p.add_argument("--document-id", required=True,
                   help='document id, or "combined" for the full envelope')
    p.add_argument("--out", required=True, help="file to write the PDF to")
    p.set_defaults(func=cmd_document_download)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
