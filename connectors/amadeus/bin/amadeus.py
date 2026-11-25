#!/usr/bin/env python3
"""Minimal Amadeus Self-Service travel API CLI for the muse-connectors amadeus skill.

Auth: loads the per-user `custom.amadeus` credential as a surrogate via the
bundled dynamic_credentials helper. Amadeus uses OAuth2 client credentials;
the runtime performs the token exchange against /v1/security/oauth2/token
and hands this script a fresh access token. The real credentials never touch
this script: the runtime swaps the surrogate on approved egress, only to the
Amadeus host in use.

This is search + pricing, not ticketing: the Self-Service APIs return offers
and prices, but do not book tickets.

Use --env test (default, free sandbox with cached/limited data) or
--env prod (real-time data with free-call tiers before billing).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

HELPER_PATH = "/opt/hatch/skills/skill-creator/bin"
CREDENTIAL_NAME = "custom.amadeus"
ALLOWED_HOSTS = ("test.api.amadeus.com", "api.amadeus.com")
BASES = {
    "test": "https://test.api.amadeus.com",
    "prod": "https://api.amadeus.com",
}

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


def call(host: str, method: str, path: str, params: dict | None = None) -> dict:
    url = host + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={}, method=method)
    try:
        add_surrogate_to_request(req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS)
    except DynamicCredentialError as exc:
        sys.exit(f"error: credential problem: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            errors = body.get("errors", [])
            msg = errors[0].get("detail", str(exc)) if errors else str(exc)
        except Exception:
            msg = str(exc)
        sys.exit(f"error: amadeus returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def cmd_auth(args):
    result = call(BASES[args.env], "GET", "/v1/reference-data/locations",
                  params={"subType": "AIRPORT", "keyword": "LHR",
                          "page[limit]": 1})
    print(json.dumps({"ok": True, "env": args.env,
                      "locations": len(result.get("data", []))}, indent=2))


def cmd_locations(args):
    result = call(BASES[args.env], "GET", "/v1/reference-data/locations",
                  params={"subType": args.sub_type, "keyword": args.keyword,
                          "page[limit]": args.limit})
    places = [
        {"iataCode": p.get("iataCode"), "name": p.get("name"),
         "subType": p.get("subType"), "type": p.get("type"),
         "address": p.get("address")}
        for p in result.get("data", [])
    ]
    print(json.dumps(places, indent=2))


def cmd_flight_offers(args):
    params = {
        "originLocationCode": args.origin,
        "destinationLocationCode": args.destination,
        "departureDate": args.departure_date,
        "adults": args.adults,
        "max": args.max,
        "currencyCode": args.currency,
    }
    if args.return_date:
        params["returnDate"] = args.return_date
    result = call(BASES[args.env], "GET", "/v2/shopping/flight-offers",
                  params=params)
    offers = []
    for o in result.get("data", []):
        price = o.get("price", {})
        legs = []
        for it in o.get("itineraries", []):
            segs = it.get("segments", [])
            legs.append({
                "duration": it.get("duration"),
                "segments": [
                    {"from": s.get("departure", {}).get("iataCode"),
                     "to": s.get("arrival", {}).get("iataCode"),
                     "carrier": s.get("carrierCode"),
                     "number": s.get("number")}
                    for s in segs
                ],
            })
        offers.append({"id": o.get("id"), "price": price.get("total"),
                       "currency": price.get("currency"),
                       "oneWay": o.get("oneWay"), "legs": legs})
    print(json.dumps(offers, indent=2))


def cmd_hotel_offers(args):
    result = call(BASES[args.env], "GET", "/v3/shopping/hotel-offers",
                  params={"hotelIds": args.hotel_ids,
                          "checkInDate": args.check_in,
                          "checkOutDate": args.check_out,
                          "adults": args.adults,
                          "currency": args.currency})
    offers = [
        {"hotel": (h.get("hotel") or {}).get("name"),
         "hotelId": h.get("hotelId"),
         "available": h.get("available"),
         "offers": [{"price": (off.get("price") or {}).get("total"),
                     "currency": (off.get("price") or {}).get("currency"),
                     "room": (off.get("room") or {}).get("description", {}).get("text")}
                    for off in h.get("offers", [])]}
        for h in result.get("data", [])
    ]
    print(json.dumps(offers, indent=2))


def cmd_flight_dates(args):
    result = call(BASES[args.env], "GET", "/v1/shopping/flight-dates",
                  params={"origin": args.origin, "destination": args.destination,
                          "departureDate": args.departure_date,
                          "duration": args.duration,
                          "currencyCode": args.currency})
    dates = [
        {"departureDate": d.get("departureDate"),
         "returnDate": d.get("returnDate"),
         "price": (d.get("price") or {}).get("total"),
         "currency": (d.get("price") or {}).get("currency")}
        for d in result.get("data", [])
    ]
    print(json.dumps(dates, indent=2))


def add_env(p):
    p.add_argument("--env", default="test", choices=("test", "prod"),
                   help="test sandbox (default) or production")


def main():
    parser = argparse.ArgumentParser(
        description="Amadeus travel API CLI (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth", help="verify the token")
    add_env(p)
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("locations", help="airport/city autocomplete")
    add_env(p)
    p.add_argument("--keyword", required=True, help="e.g. LON, London")
    p.add_argument("--sub-type", default="AIRPORT,CITY",
                   help="e.g. AIRPORT,CITY")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_locations)

    p = sub.add_parser("flight-offers", help="search flight offers and prices")
    add_env(p)
    p.add_argument("--origin", required=True, help="IATA code, e.g. JFK")
    p.add_argument("--destination", required=True, help="IATA code, e.g. LHR")
    p.add_argument("--departure-date", required=True, help="YYYY-MM-DD")
    p.add_argument("--return-date", default=None, help="YYYY-MM-DD")
    p.add_argument("--adults", type=int, default=1)
    p.add_argument("--max", type=int, default=10, help="max offers")
    p.add_argument("--currency", default="USD")
    p.set_defaults(func=cmd_flight_offers)

    p = sub.add_parser("hotel-offers", help="hotel offers by hotel IDs")
    add_env(p)
    p.add_argument("--hotel-ids", required=True,
                   help="comma-separated Amadeus hotel IDs")
    p.add_argument("--check-in", required=True, help="YYYY-MM-DD")
    p.add_argument("--check-out", required=True, help="YYYY-MM-DD")
    p.add_argument("--adults", type=int, default=1)
    p.add_argument("--currency", default="USD")
    p.set_defaults(func=cmd_hotel_offers)

    p = sub.add_parser("flight-dates", help="cheapest travel dates for a route")
    add_env(p)
    p.add_argument("--origin", required=True, help="IATA code")
    p.add_argument("--destination", required=True, help="IATA code")
    p.add_argument("--departure-date", required=True,
                   help="start of search window, YYYY-MM-DD")
    p.add_argument("--duration", type=int, default=7,
                   help="trip length in days")
    p.add_argument("--currency", default="USD")
    p.set_defaults(func=cmd_flight_dates)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
