#!/usr/bin/env python3
"""Datawright Labs web tools CLI for the muse-connectors datawright skill.

Runs one of the Datawright Labs Actors on Apify (synchronously, via the
documented run-sync-get-dataset-items endpoint) and prints its result rows.

Auth: loads the per-user `custom.datawright` credential (an Apify API token)
as a surrogate via the bundled dynamic_credentials helper; the runtime swaps
the surrogate on approved egress, only to api.apify.com. Outside a Muse
runtime it falls back to the APIFY_TOKEN environment variable. The token is
never accepted as a command-line argument and never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.datawright"
ALLOWED_HOSTS = ("api.apify.com",)
API = "https://api.apify.com"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (  # type: ignore
        DynamicCredentialError,
        add_surrogate_to_request,
        read_json_response,
    )
    HAVE_HELPER = True
except ImportError:
    HAVE_HELPER = False

# tool: (actor, what it does, list input field, price per result)
TOOLS = {
    "dns": ("email-domain-dns-checker", "SPF, DMARC, DKIM, MX, MTA-STS per domain", "domains", "$0.001 per domain"),
    "ssl": ("ssl-certificate-checker", "SSL certificate expiry, issuer, trust + domain expiry", "domains", "$0.001 per host"),
    "whois": ("whois-rdap-domain-lookup", "WHOIS/RDAP: registrar, domain age, expiry, availability", "domains", "$0.001 per domain"),
    "links": ("broken-link-checker", "crawl sites and report broken links / 404s", "startUrls", "$0.0005 per unique URL checked"),
    "pagespeed": ("pagespeed-auditor", "Lighthouse scores and Core Web Vitals", "urls", "$0.015 per audit (URL x device)"),
    "screenshot": ("website-screenshot", "screenshots / PDFs of URLs, returns image links", "urls", "$0.0015 per screenshot + $0.0015 per run"),
    "sitemap": ("sitemap-url-extractor", "every URL in a site's sitemaps", "startUrls", "$0.0002 per URL"),
    "autocomplete": ("autocomplete-keyword-scraper", "Google/YouTube/Bing autocomplete keyword ideas", "keywords", "$0.0002 per suggestion"),
    "appcharts": ("app-store-top-charts", "Apple App Store top charts (pass --input)", None, "$0.001 per chart entry"),
    "jobs": ("ats-jobs-scraper", "open jobs from Greenhouse/Lever/Ashby/Workable/SmartRecruiters boards", "companies", "$0.001 per job"),
}


def call(method: str, path: str, params: dict | None = None,
         payload: dict | None = None, timeout: int = 60):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    if HAVE_HELPER:
        try:
            add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
        except DynamicCredentialError as exc:
            sys.exit(f"error: credential problem: {exc}")
    else:
        token = os.environ.get("APIFY_TOKEN", "").strip()
        if not token:
            sys.exit("error: no credential: run inside Muse (custom.datawright) or set APIFY_TOKEN")
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout + 30) as resp:
            if HAVE_HELPER:
                return read_json_response(resp)
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            msg = body.get("error", {}).get("message", str(exc)) if isinstance(body.get("error"), dict) else str(body)[:300]
        except Exception:
            msg = str(exc)
        sys.exit(f"error: apify returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(_args):
    me = call("GET", "/v2/users/me").get("data", {})
    print(json.dumps({"ok": True, "username": me.get("username")}, indent=2))


def cmd_tools(_args):
    print(json.dumps({k: {"actor": "datawright-labs/" + v[0], "does": v[1], "price": v[3]}
                      for k, v in TOOLS.items()}, indent=2))


def cmd_run(args):
    actor, _does, field, price = TOOLS[args.tool]
    if args.input:
        payload = json.loads(args.input)
    elif field and args.targets:
        payload = {field: args.targets}
    else:
        sys.exit("error: pass targets or --input (full Actor input as JSON)")
    if not args.confirm:
        print(json.dumps({"ok": False, "needs_confirmation": True, "actor": "datawright-labs/" + actor,
                          "input": payload, "price": price, "max_cost_usd": args.max_cost,
                          "note": "nothing was run; re-run with --confirm after the user agrees"}, indent=2))
        return
    params = {"timeout": args.timeout, "format": "json", "maxTotalChargeUsd": args.max_cost}
    rows = call("POST", f"/v2/acts/datawright-labs~{actor}/run-sync-get-dataset-items",
                params=params, payload=payload, timeout=args.timeout)
    print(json.dumps(rows, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Datawright Labs web tools on Apify (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("auth", help="verify the Apify token (free)")
    p.set_defaults(func=cmd_auth)
    p = sub.add_parser("tools", help="list tools and prices (free)")
    p.set_defaults(func=cmd_tools)
    p = sub.add_parser("run", help="run a tool (paid; needs --confirm)")
    p.add_argument("tool", choices=TOOLS)
    p.add_argument("targets", nargs="*", help="domains, URLs or keywords")
    p.add_argument("--input", help="full Actor input as JSON (overrides targets)")
    p.add_argument("--timeout", type=int, default=240, help="seconds to wait for the run")
    p.add_argument("--max-cost", type=float, default=0.5, help="hard spending cap for this run in USD")
    p.add_argument("--confirm", action="store_true", help="actually run (the user agreed to the cost)")
    p.set_defaults(func=cmd_run)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
