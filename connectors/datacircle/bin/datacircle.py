#!/usr/bin/env python3
"""Datacircle CLI for the muse-connectors datacircle skill (standard library only).

Calls the open Datacircle API, https://api.datacircle.dev/v1 (its spec:
https://api.datacircle.dev/v1/openapi.json). No key, no account, no credential.

Prints the API's answer as JSON. Exits 0 on HTTP 200, 2 on another HTTP answer
(its JSON still printed), 3 when the API can't be reached.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.datacircle.dev/v1"  # the spec's servers[0].url
TIMEOUT_SECONDS = 30


def call(path: str, query: dict | None = None) -> int:
    params = {k: v for k, v in (query or {}).items() if v is not None}
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "muse-connectors-datacircle/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            print(json.dumps(json.loads(resp.read().decode("utf-8")), indent=2, ensure_ascii=False))
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            answer = json.loads(body)
        except json.JSONDecodeError:
            answer = {"error": body[:300]}
        out = {"http_status": exc.code, **(answer if isinstance(answer, dict) else {"answer": answer})}
        if exc.code == 429:
            out["retry_after_seconds"] = exc.headers.get("Retry-After")
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 2
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(json.dumps({"http_status": None, "error": f"request failed: {exc}"}, indent=2))
        return 3


def cmd_status(_args) -> int:
    req = urllib.request.Request(API + "/apis", headers={"Accept": "application/json", "User-Agent": "muse-connectors-datacircle/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            apis = json.loads(resp.read().decode("utf-8"))
        print(json.dumps({"ok": True, "apis": len(apis)}, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - any failure is reported, never a crash
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 3


def cmd_apis(_args) -> int:
    return call("/apis")


def cmd_best(args) -> int:
    return call(f"/apis/{urllib.parse.quote(args.api, safe='')}/best", {"limit": args.limit})


def cmd_plans(args) -> int:
    return call("/plans", {"api": args.api, "query": args.query, "sort": args.sort, "limit": args.limit, "offset": args.offset})


def cmd_provider(args) -> int:
    return call(f"/providers/{urllib.parse.quote(args.slug, safe='')}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Datacircle CLI (muse-connectors): the open Datacircle API, no key.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="check the API answers")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("apis", help="GET /apis: every API on the sheet, its slug, its plans and its best plan")
    p.set_defaults(func=cmd_apis)

    p = sub.add_parser("best", help="GET /apis/{slug}/best: an API's plans, best first by score")
    p.add_argument("--api", required=True, help="the API's slug, as `apis` gives it (e.g. email-finder)")
    p.add_argument("--limit", type=int, help="how many plans, 1 to 50 (10 when left out)")
    p.set_defaults(func=cmd_best)

    p = sub.add_parser("plans", help="GET /plans: search every plan, by API, provider or plan name")
    p.add_argument("--api", help="the API, its name or its slug (every API when left out)")
    p.add_argument("--query", help="words that must all be in the provider's or plan's name")
    p.add_argument("--sort", choices=["score", "provider", "price"], help="score (default), provider A to Z, or price per 1,000")
    p.add_argument("--limit", type=int, help="how many plans, 1 to 50 (10 when left out)")
    p.add_argument("--offset", type=int, help="how many found plans to skip first")
    p.set_defaults(func=cmd_plans)

    p = sub.add_parser("provider", help="GET /providers/{slug}: one provider's plans and rank on each API")
    p.add_argument("--slug", required=True, help="the provider's slug, e.g. bright-data")
    p.set_defaults(func=cmd_provider)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
