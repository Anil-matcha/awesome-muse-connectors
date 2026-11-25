#!/usr/bin/env python3
"""Typeform API CLI for the muse-connectors typeform skill.

Auth: personal access token sent as `Authorization: Bearer <token>`. The
user stores the token through the secure credential flow
(credentials.request_api_access) and the runtime hands this script a fresh
token via the bundled dynamic_credentials helper. The real token never
touches this script: the runtime swaps the surrogate on approved egress,
only to api.typeform.com.

Writes (form-create, webhook-create, webhook-delete) require an exact
--confirm string echoed by the CLI, on every call.
HONESTY NOTE: endpoint paths are taken from Typeform's public developer
docs and have not been verified in a live flow. In particular the webhook
create path (PUT /forms/{form_id}/webhooks/{tag}) and the create-form
body shape ({"type", "title", "fields"}) are provisional; if form-create
rejects the body, check Typeform's current docs for the required shape.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.typeform"
ALLOWED_HOSTS = ("api.typeform.com",)
BASE = "https://api.typeform.com"
CONNECT_GUIDANCE = (
    "not connected: store a Typeform personal access token (Typeform "
    "account > Settings > Personal tokens) via the secure credential flow "
    "(credentials.request_api_access) as `custom.typeform`, then retry."
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


def call(method: str, path: str, payload: dict | None = None) -> dict:
    url = BASE + path
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
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
            if resp.status == 204:
                return {"ok": True}
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("description", str(exc))
        except Exception:
            msg = str(exc)
        sys.exit(f"error: typeform returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def need_confirm(args, expected: str, effect: str) -> None:
    """Refuse unless --confirm matches the exact effect string."""
    if args.confirm == expected:
        return
    sys.exit(
        f"refusing: {effect}\n"
        f"Re-run with the exact confirmation string:\n"
        f'  --confirm "{expected}"'
    )


def slim_answer(a: dict) -> dict:
    field = a.get("field", {}) or {}
    out = {"field_id": field.get("id"), "field_type": a.get("type")}
    for key in ("text", "email", "url", "choice", "choices", "number",
                "boolean", "date", "phone_number"):
        if key in a:
            val = a[key]
            if isinstance(val, dict):
                out[key] = val.get("label", val)
            else:
                out[key] = val
    return out


def cmd_auth(args):
    result = call("GET", "/me")
    print(json.dumps({"ok": True, "user_id": result.get("user_id"),
                      "email": result.get("email"),
                      "alias": result.get("alias")}, indent=2))


def cmd_forms(args):
    result = call("GET", f"/forms?page_size={args.limit}")
    items = [{"id": f.get("id"), "title": f.get("title"),
              "last_updated_at": f.get("last_updated_at")}
             for f in result.get("items", [])]
    print(json.dumps(items, indent=2))


def cmd_form_get(args):
    result = call("GET", f"/forms/{args.form_id}")
    fields = [{"id": f.get("id"), "title": f.get("title"),
               "type": f.get("type")}
              for f in result.get("fields", [])]
    print(json.dumps({"id": result.get("id"), "title": result.get("title"),
                      "theme": (result.get("theme") or {}).get("href"),
                      "fields": fields}, indent=2))


def cmd_responses(args):
    query = f"?page_size={args.limit}"
    if args.since:
        query += f"&since={args.since}"
    result = call("GET", f"/forms/{args.form_id}/responses{query}")
    items = []
    for r in result.get("items", []):
        items.append({"response_id": r.get("response_id"),
                      "landed_at": r.get("landed_at"),
                      "submitted_at": r.get("submitted_at"),
                      "answers": [slim_answer(a) for a in r.get("answers", [])]})
    print(json.dumps(items, indent=2))


def cmd_webhooks_list(args):
    result = call("GET", f"/forms/{args.form_id}/webhooks")
    print(json.dumps([{"tag": w.get("tag"), "url": w.get("url"),
                       "enabled": w.get("enabled"),
                       "verify_ssl": w.get("verify_ssl")}
                      for w in result], indent=2))


def cmd_form_create(args):
    try:
        fields = json.loads(args.fields_json)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: --fields-json is not valid JSON: {exc}")
    if not isinstance(fields, list) or not fields:
        sys.exit("error: --fields-json must be a non-empty JSON array of "
                 "field objects")
    for f in fields:
        if not isinstance(f, dict) or "title" not in f or "type" not in f:
            sys.exit("error: every field needs at least a title and a type, "
                     f"got: {f!r}")
    expected = f'create form "{args.title}" with {len(fields)} field(s)'
    need_confirm(
        args, expected,
        f"creating a new Typeform titled {args.title!r} with "
        f"{len(fields)} field(s).")
    # The "type" key ("form" or "quiz") is what public docs/examples show
    # on create-form bodies; kept as a flag because it is not certain the
    # API requires it or which values are accepted.
    result = call("POST", "/forms",
                  {"type": args.type, "title": args.title,
                   "fields": fields})
    print(json.dumps({"ok": True, "form_id": result.get("id"),
                      "title": result.get("title"),
                      "url": (result.get("_links") or {}).get("display")},
                     indent=2))


def cmd_webhook_create(args):
    expected = (f"create webhook {args.tag} on form {args.form_id} "
                f"for {args.url}")
    need_confirm(
        args, expected,
        f"creating webhook {args.tag} posts every new response of form "
        f"{args.form_id} to {args.url}; the endpoint will receive "
        "respondent data.")
    result = call("PUT", f"/forms/{args.form_id}/webhooks/{args.tag}",
                  {"url": args.url, "enabled": True})
    print(json.dumps({"ok": True, "tag": result.get("tag"),
                      "url": result.get("url"),
                      "enabled": result.get("enabled")}, indent=2))


def cmd_webhook_delete(args):
    expected = f"delete webhook {args.tag} on form {args.form_id}"
    need_confirm(
        args, expected,
        f"deleting webhook {args.tag} stops all response delivery to its "
        "endpoint.")
    call("DELETE", f"/forms/{args.form_id}/webhooks/{args.tag}")
    print(json.dumps({"ok": True, "tag": args.tag,
                      "form_id": args.form_id, "deleted": True}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Typeform API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the token (GET /me)")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("forms", help="list forms")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_forms)

    p = sub.add_parser("form-get", help="fetch one form and its fields")
    p.add_argument("--form-id", required=True)
    p.set_defaults(func=cmd_form_get)

    p = sub.add_parser("responses", help="list form responses")
    p.add_argument("--form-id", required=True)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--since", default=None,
                   help="only responses after this ISO timestamp")
    p.set_defaults(func=cmd_responses)

    p = sub.add_parser("form-create",
                       help="create a new form (needs --confirm)")
    p.add_argument("--title", required=True)
    p.add_argument("--fields-json", required=True,
                   help='JSON array of field objects, e.g. '
                        '\'[{"title": "Your name", "type": "short_text", '
                        '"validations": {"required": true}}, '
                        '{"title": "Rate us", "type": "rating", '
                        '"properties": {"steps": 5}}]\' '
                        '(field types: short_text, long_text, multiple_choice, '
                        'dropdown, email, number, yes_no, opinion_scale, '
                        'rating, statement, contact_info, ...)')
    p.add_argument("--type", default="form", choices=("form", "quiz"),
                   help="form type (default: form)")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_form_create)

    p = sub.add_parser("webhooks-list", help="list a form's webhooks")
    p.add_argument("--form-id", required=True)
    p.set_defaults(func=cmd_webhooks_list)

    p = sub.add_parser("webhook-create",
                       help="create a form webhook (needs --confirm)")
    p.add_argument("--form-id", required=True)
    p.add_argument("--tag", required=True,
                   help="webhook name; reusing an existing tag overwrites it")
    p.add_argument("--url", required=True,
                   help="HTTPS endpoint receiving responses")
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_webhook_create)

    p = sub.add_parser("webhook-delete",
                       help="delete a form webhook (needs --confirm)")
    p.add_argument("--form-id", required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--confirm", default=None)
    p.set_defaults(func=cmd_webhook_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
