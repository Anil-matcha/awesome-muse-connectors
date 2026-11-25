#!/usr/bin/env python3
"""Minimal OpenWeatherMap CLI for the muse-connectors openweathermap skill.

Auth: loads the per-user `custom.openweathermap` credential as a surrogate via
the bundled dynamic_credentials helper. The real API key never touches this
script: the runtime swaps the surrogate into the `appid` query param on
approved egress, only to api.openweathermap.org.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.openweathermap"
ALLOWED_HOSTS = ("api.openweathermap.org",)
API = "https://api.openweathermap.org/data/2.5"

try:
    sys.path.insert(0, HELPER_PATH)
    from dynamic_credentials import (
        DynamicCredentialError,
        read_json_response,
        url_with_surrogate_query_param,
    )
except ImportError:
    sys.exit(
        "error: this CLI needs the Muse dynamic_credentials helper at "
        f"{HELPER_PATH} (install this skill on a Muse runtime to use it)"
    )


def call_get(path: str, params: dict) -> dict:
    url = API + path + "?" + urllib.parse.urlencode(params)
    try:
        url = url_with_surrogate_query_param(
            url, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS
        )
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        sys.exit(f"error: HTTP {exc.code}: {body[:300]}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_weather(args):
    result = call_get("/weather", {"q": args.city, "units": "metric"})
    out = {
        "city": result.get("name"),
        "country": (result.get("sys") or {}).get("country"),
        "temp_c": (result.get("main") or {}).get("temp"),
        "feels_like_c": (result.get("main") or {}).get("feels_like"),
        "humidity": (result.get("main") or {}).get("humidity"),
        "description": (result.get("weather") or [{}])[0].get("description"),
    }
    print(json.dumps(out, indent=2))


def cmd_forecast(args):
    result = call_get("/forecast", {"q": args.city, "units": "metric"})
    out = [
        {
            "dt_txt": item.get("dt_txt"),
            "temp_c": (item.get("main") or {}).get("temp"),
            "description": (item.get("weather") or [{}])[0].get("description"),
        }
        for item in result.get("list", [])[:8]
    ]
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="OpenWeatherMap CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("weather", help="current weather for a city")
    p.add_argument("--city", required=True)
    p.set_defaults(func=cmd_weather)

    p = sub.add_parser("forecast", help="5-day forecast (first 8 slots) for a city")
    p.add_argument("--city", required=True)
    p.set_defaults(func=cmd_forecast)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
