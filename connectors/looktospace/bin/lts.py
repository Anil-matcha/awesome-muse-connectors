#!/usr/bin/env python3
"""lts - LookToSpace connector CLI.

Visibility answers come from the site's own API
(https://looktospace.com/api/v1/visibility): the site is the single source
of truth for tiers. Launch Library 2 is used directly only for schedule
data (and schedule-only fallback). No API keys needed.

Subcommands:
  lts geocode <query>                  Resolve a city/ZIP to lat/lon (JSON).
  lts upcoming [--limit N]             Upcoming launches, LL2 schedule (cached).
  lts visible --location <query> [--limit N] [--days N] [--visible-only]
                                       Launches + per-location visibility (JSON).
  lts launch <ll2-id>                  One launch in detail (JSON).
"""
import argparse, json, os, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone

UA = {"User-Agent": "looktospace-connector/0.1 (Muse skill)"}
CACHE_DIR = os.path.expanduser("~/.cache/looktospace")
LL2_BASE = "https://ll.thespacedevs.com/2.3.0"
GEOCODE_BASE = "https://geocoding-api.open-meteo.com/v1/search"
SITE = "https://looktospace.com"
SITE_API = SITE + "/api/v1/visibility"
SITE_FEED = SITE + "/api/launches"


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def cache_path(name):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)


def cache_get(name, ttl_s):
    p = cache_path(name)
    try:
        with open(p) as f:
            d = json.load(f)
        if time.time() - d["ts"] < ttl_s:
            return d["data"]
    except (OSError, ValueError, KeyError):
        pass
    return None


def cache_put(name, data):
    with open(cache_path(name), "w") as f:
        json.dump({"ts": time.time(), "data": data}, f)


def geocode(query):
    key = "geo_" + "".join(c if c.isalnum() else "_" for c in query.lower())[:60] + ".json"
    hit = cache_get(key, 30 * 86400)
    if hit:
        return hit
    tries = [query]
    toks = query.split()
    if len(toks) > 1:
        tries.append(toks[0])
    for q in tries:
        url = GEOCODE_BASE + "?" + urllib.parse.urlencode(
            {"name": q, "count": 5, "language": "en", "format": "json"})
        try:
            d = get(url)
        except Exception:
            continue
        for r in d.get("results", []):
            label = r["name"]
            if r.get("admin1"):
                label += ", " + r["admin1"]
            label += ", " + r.get("country", "")
            out = {"label": label, "latitude": r["latitude"],
                   "longitude": r["longitude"], "country_code": r.get("country_code", "")}
            cache_put(key, out)
            return out
    raise SystemExit(f"Could not geocode '{query}'. Try a city name or US ZIP code.")


def site_paths():
    """Map LL2 launch id -> canonical site path, from the site's own feed.

    Never slugify names locally: the site's slug algorithm handles
    collisions and truncation, and a wrong slug silently 301s to the
    launches index. Returns {} on failure (caller must handle None)."""
    hit = cache_get("site_paths.json", 15 * 60)
    if hit is None:
        try:
            d = get(SITE_FEED + "?" + urllib.parse.urlencode({"full": 1, "limit": 200}))
            hit = {l.get("id"): l.get("path") for l in d.get("launches", [])
                   if l.get("id") and l.get("path")}
        except Exception:
            hit = {}
        cache_put("site_paths.json", hit)
    return hit


def upcoming(limit=25):
    hit = cache_get("upcoming_v3.json", 30 * 60)
    if hit is None:
        url = (LL2_BASE + "/launches/upcoming/?" + urllib.parse.urlencode(
            {"limit": 60, "mode": "detailed"}))
        try:
            d = get(url)
        except Exception as e:
            raise SystemExit(f"Launch Library 2 request failed: {e}. "
                             "Cached data may be stale; try again shortly.")
        launches = []
        for l in d.get("results", []):
            pad = l.get("pad") or {}
            launches.append({
                "id": l.get("id"), "name": l.get("name"), "net": l.get("net"),
                "status": (l.get("status") or {}).get("name"),
                "provider": (l.get("launch_service_provider") or {}).get("name"),
                "rocket": ((l.get("rocket") or {}).get("configuration") or {}).get("full_name"),
                "pad_name": pad.get("name"),
                "pad_lat": pad.get("latitude"), "pad_lon": pad.get("longitude"),
                "webcast": l.get("webcast_live"),
                "site_url": None,  # filled from the site's canonical paths below
            })
        paths = site_paths()
        for l in launches:
            p = paths.get(l["id"])
            l["site_url"] = (SITE + p) if p else None
        hit = launches
        cache_put("upcoming_v3.json", hit)
    return hit[:limit]


def parse_net(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def countdown(dt):
    secs = int((dt - datetime.now(timezone.utc)).total_seconds())
    if secs <= 0:
        return "already launched" if secs > -7200 else "launched"
    d, r = divmod(secs, 86400)
    h, r = divmod(r, 3600)
    m, _ = divmod(r, 60)
    return f"{d}d {h:02d}h {m:02d}m" if d else f"{h}h {m:02d}m"


def cmd_geocode(a):
    print(json.dumps(geocode(a.query), indent=2))


def cmd_upcoming(a):
    print(json.dumps(upcoming(a.limit), indent=2))


def cmd_launch(a):
    url = LL2_BASE + "/launches/%s/?mode=detailed" % urllib.parse.quote(a.ll2_id, safe="")
    try:
        l = get(url)
    except Exception as e:
        raise SystemExit(f"Launch Library 2 request failed: {e}")
    pad = l.get("pad") or {}
    lid = l.get("id")
    p = site_paths().get(lid)
    print(json.dumps({
        "id": lid, "name": l.get("name"), "net": l.get("net"),
        "status": (l.get("status") or {}).get("name"),
        "provider": (l.get("launch_service_provider") or {}).get("name"),
        "rocket": ((l.get("rocket") or {}).get("configuration") or {}).get("full_name"),
        "mission": (l.get("mission") or {}).get("description"),
        "pad_name": pad.get("name"), "pad_lat": pad.get("latitude"),
        "pad_lon": pad.get("longitude"), "webcast": l.get("webcast_live"),
        "site_url": (SITE + p) if p else None,
    }, indent=2))


def cmd_visible(a):
    loc = geocode(a.location)
    params = {
        "lat": round(loc["latitude"], 5), "lon": round(loc["longitude"], 5),
        "limit": a.limit, "days": a.days,
        "label": loc["label"][:80], "ref": "muse",
    }
    if a.visible_only:
        params["visible_only"] = 1
    url = SITE_API + "?" + urllib.parse.urlencode(params)
    try:
        d = get(url)
    except Exception as e:
        return fallback_schedule(a, loc, str(e))
    out = {"location": d.get("location", loc), "results": [],
           "generatedAt": d.get("generatedAt"), "fetchedAt": d.get("fetchedAt")}
    if d.get("stale"):
        out["stale"] = True
    for r in d.get("results", []):
        dt = parse_net(r["net_utc"])
        out["results"].append({
            "id": r.get("id"),
            "name": r.get("name"),
            "net_utc": r.get("net_utc"),
            "countdown": countdown(dt),
            "net_precision": r.get("net_precision"),
            "time_uncertain": r.get("time_uncertain", False),
            "status": r.get("status"),
            "provider": r.get("provider"),
            "rocket": r.get("rocket"),
            "pad": r.get("pad"),
            "site": r.get("site"),
            "distance_mi": r.get("distance_mi"),
            "look_toward": r.get("look_toward"),
            "lighting": r.get("lighting"),
            "visibility": r.get("visibility"),
            "visible": r.get("visible"),
            "site_url": r.get("site_url"),
        })
    print(json.dumps(out, indent=2))


def fallback_schedule(a, loc, err):
    """Site API unreachable: schedule only, no visibility tiers.

    The site is the single source of truth for tiers, so the local engine
    is never used as a substitute."""
    out = {"location": loc, "results": [],
           "visibility_unavailable": "site API unreachable (%s); showing schedule only" % err}
    for l in upcoming(a.limit):
        dt = parse_net(l["net"])
        out["results"].append({
            "name": l["name"], "net_utc": l["net"], "countdown": countdown(dt),
            "status": l["status"], "provider": l["provider"], "pad": l["pad_name"],
            "visibility": None, "site_url": l.get("site_url"),
        })
    print(json.dumps(out, indent=2))


def main():
    p = argparse.ArgumentParser(prog="lts")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("geocode"); g.add_argument("query"); g.set_defaults(f=cmd_geocode)
    u = sub.add_parser("upcoming")
    u.add_argument("--limit", type=int, default=15); u.set_defaults(f=cmd_upcoming)
    v = sub.add_parser("visible")
    v.add_argument("--location", required=True)
    v.add_argument("--limit", type=int, default=10)
    v.add_argument("--days", type=int, default=60)
    v.add_argument("--visible-only", action="store_true"); v.set_defaults(f=cmd_visible)
    d = sub.add_parser("launch"); d.add_argument("ll2_id"); d.set_defaults(f=cmd_launch)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
