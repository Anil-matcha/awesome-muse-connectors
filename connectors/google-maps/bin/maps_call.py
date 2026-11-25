#!/usr/bin/env python3
"""Google Maps Platform client (Routes + Geocoding) using the vault-stored
custom.google-maps credential via the dynamic_credentials surrogate.
Never prints or persists the raw key.

Usage:
  maps_call.py auth
  maps_call.py route --from "New York, NY" --to "Boston, MA" [--mode DRIVE|TRANSIT|WALK|BICYCLE]
  maps_call.py geocode --address "350 5th Ave, New York, NY"
  maps_call.py reverse --lat 40.7484 --lng -73.9857
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import (
    url_with_surrogate_query_param,
    read_json_response,
    DynamicCredentialError,
)

ALLOWED = ["routes.googleapis.com", "maps.googleapis.com"]
CRED = "custom.google-maps"
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def _send(req):
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = {"error": f"HTTP {e.code}"}
        return e.code, payload


def _geocode(address):
    q = urllib.parse.urlencode({"address": address})
    url = url_with_surrogate_query_param(
        f"{GEOCODE_URL}?{q}", CRED, allowed_hosts=ALLOWED)
    return _send(urllib.request.Request(url, method="GET"))


def cmd_auth(_args):
    status, payload = _geocode("New York, NY")
    ok = status == 200 and payload.get("status") == "OK"
    print(json.dumps({"ok": ok, "status": status,
                      "api_status": payload.get("status")}))
    return 0 if ok else 1


def cmd_route(args):
    def wp(v):
        try:
            lat, lng = v.split(",")
            return {"location": {"latLng": {
                "latitude": float(lat), "longitude": float(lng)}}}
        except Exception:
            return {"address": v}

    body = {
        "origin": wp(args.from_), "destination": wp(args.to),
        "travelMode": args.mode, "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False, "units": "IMPERIAL",
        "languageCode": "en-US",
    }
    if args.mode == "TRANSIT":
        body.pop("routingPreference", None)
    url = url_with_surrogate_query_param(ROUTES_URL, CRED, allowed_hosts=ALLOWED)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header(
        "X-Goog-FieldMask",
        "routes.duration,routes.staticDuration,routes.distanceMeters,"
        "routes.description,routes.legs.steps.transitDetails,"
        "routes.polyline.encodedPolyline")
    status, payload = _send(req)
    out = {"status": status}
    routes = payload.get("routes") or []
    if routes:
        r = routes[0]
        out["route"] = {
            "duration": r.get("duration"),
            "staticDuration": r.get("staticDuration"),
            "distanceMeters": r.get("distanceMeters"),
            "description": r.get("description"),
        }
    else:
        out["payload"] = payload
    print(json.dumps(out, indent=1))
    return 0 if status == 200 and routes else 1


def cmd_geocode(args):
    status, payload = _geocode(args.address)
    print(json.dumps({"status": status, "payload": payload}, indent=1)[:4000])
    return 0 if status == 200 and payload.get("status") == "OK" else 1


def cmd_reverse(args):
    q = urllib.parse.urlencode({"latlng": f"{args.lat},{args.lng}"})
    url = url_with_surrogate_query_param(
        f"{GEOCODE_URL}?{q}", CRED, allowed_hosts=ALLOWED)
    status, payload = _send(urllib.request.Request(url, method="GET"))
    print(json.dumps({"status": status, "payload": payload}, indent=1)[:4000])
    return 0 if status == 200 and payload.get("status") == "OK" else 1


def main():
    p = argparse.ArgumentParser(description="Maps Platform CLI (vault credential)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("auth", help="verify the stored credential")

    r = sub.add_parser("route")
    r.add_argument("--from", dest="from_", required=True)
    r.add_argument("--to", required=True)
    r.add_argument("--mode", default="DRIVE",
                   choices=["DRIVE", "TRANSIT", "WALK", "BICYCLE"])

    g = sub.add_parser("geocode")
    g.add_argument("--address", required=True)

    v = sub.add_parser("reverse")
    v.add_argument("--lat", type=float, required=True)
    v.add_argument("--lng", type=float, required=True)

    args = p.parse_args()
    try:
        if args.cmd == "auth":
            return cmd_auth(args)
        if args.cmd == "route":
            return cmd_route(args)
        if args.cmd == "geocode":
            return cmd_geocode(args)
        return cmd_reverse(args)
    except DynamicCredentialError as e:
        print(json.dumps({"error": f"credential: {e}"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
