#!/usr/bin/env python3
"""Market Evidence Check CLI (standard library only).

Implements the public OpenAPI contract:
  GET  {BASE_URL}/__devday_healthz
  POST {BASE_URL}/v1/evidence/check

No authentication. Prints a single JSON object to stdout: the API response
with an added "http_status" field. Exits 0 for HTTP 200, 2 for non-200 HTTP
responses (JSON still printed), 3 for transport errors (JSON error printed).
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

BASE_URL = "https://devday.167-179-82-72.nip.io"  # from OpenAPI servers[0].url
TIMEOUT_SECONDS = 20


def call(method, path, payload=None):
    url = BASE_URL + path
    data = None
    headers = {"Accept": "application/json", "User-Agent": "market-evidence-check-cli/1.0"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8", "replace")
            parsed = json.loads(body) if body else {}
            if not isinstance(parsed, dict):
                parsed = {"response": parsed}
            out = {"http_status": resp.status}
            out.update(parsed)
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body) if body else {}
            if not isinstance(parsed, dict):
                parsed = {"response": parsed}
        except json.JSONDecodeError:
            parsed = {"raw_body": body}
        out = {"http_status": e.code}
        out.update(parsed)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 2
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        # Fail closed: transport errors are reported, never converted to GO.
        out = {
            "http_status": None,
            "decision": "WATCH",
            "reason_codes": ["TRANSPORT_ERROR"],
            "report_status": "TECHNICAL_FAILURE",
            "detail": str(e),
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 3


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only Market Evidence Check CLI (no auth).")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="GET /__devday_healthz")

    p_check = sub.add_parser("check", help="POST /v1/evidence/check")
    p_check.add_argument("--instrument", required=True, help="OKX instrument ID, e.g. BTC-USDT")
    p_check.add_argument("--side", required=True, help='buy or sell (validated by the API)')
    p_check.add_argument("--notional-usdt", required=True, type=float, help="Hypothetical size in USDT")
    p_check.add_argument("--max-cost-bps", type=float, default=30, help="Max estimated one-way cost bps (default 30)")

    args = parser.parse_args(argv)

    if args.command == "health":
        return call("GET", "/__devday_healthz")

    payload = {
        "instrument": args.instrument,
        "side": args.side,
        "notional_usdt": args.notional_usdt,
        "max_cost_bps": args.max_cost_bps,
    }
    return call("POST", "/v1/evidence/check", payload)


if __name__ == "__main__":
    sys.exit(main())
