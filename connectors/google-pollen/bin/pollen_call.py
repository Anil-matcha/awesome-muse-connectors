#!/usr/bin/env python3
"""Google Pollen API caller using the stored custom.google-pollen credential.

Prints forecast:lookup JSON. Never prints or persists the raw key.

Usage:
  pollen_call.py auth
  pollen_call.py forecast --lat 40.7128 --lng -74.0060 [--days 1-5] [--json]
"""
import argparse
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import (
    url_with_surrogate_query_param,
    read_json_response,
    DynamicCredentialError,
)

BASE = "https://pollen.googleapis.com/v1/forecast:lookup"
ALLOWED = ["pollen.googleapis.com"]
CRED = "custom.google-pollen"


def lookup(lat, lng, days=1):
    url = (
        f"{BASE}?location.latitude={lat}&location.longitude={lng}"
        f"&days={days}&languageCode=en"
    )
    url = url_with_surrogate_query_param(url, CRED, allowed_hosts=ALLOWED)
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = {"error": f"HTTP {e.code}"}
        return e.code, payload


def cmd_auth(_args):
    # A one-day lookup verifies that the stored credential is accepted without
    # exposing it. New York City is used only as a public test location.
    status, payload = lookup(40.7128, -74.0060, days=1)
    ok = status == 200
    print(json.dumps({"ok": ok, "status": status}))
    return 0 if ok else 1


def cmd_forecast(args):
    status, payload = lookup(args.lat, args.lng, days=args.days)
    print(json.dumps({"status": status, "payload": payload}, indent=2)[:12000])
    return 0 if status == 200 else 1


def main():
    parser = argparse.ArgumentParser(description="Google Pollen API CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("auth", help="verify the stored credential")

    forecast = sub.add_parser("forecast", help="look up a pollen forecast")
    forecast.add_argument("--lat", type=float, required=True)
    forecast.add_argument("--lng", type=float, required=True)
    forecast.add_argument("--days", type=int, default=1, choices=range(1, 6))
    forecast.add_argument("--json", action="store_true",
                          help="accepted for explicit JSON output (the default)")

    args = parser.parse_args()
    try:
        if args.cmd == "auth":
            return cmd_auth(args)
        return cmd_forecast(args)
    except DynamicCredentialError as e:
        print(json.dumps({"error": f"credential: {e}"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
