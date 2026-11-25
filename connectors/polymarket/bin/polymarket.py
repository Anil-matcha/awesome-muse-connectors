#!/usr/bin/env python3
"""Read-only Polymarket Gamma API CLI for the muse-connectors polymarket
skill.

No credential is needed: the Gamma API is public. Order-book snapshots come
from the public CLOB REST endpoint. This connector ships no trading actions:
no order placement, no positions, nothing signed. Market data only.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
ALLOWED_PREFIXES = (GAMMA_BASE, CLOB_BASE)


def get(url: str):
    if not url.startswith(ALLOWED_PREFIXES):
        sys.exit(f"refusing: url outside allowed hosts: {url}")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            msg = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            msg = str(exc)
        sys.exit(f"error: polymarket returned HTTP {exc.code}: {msg}")
    except Exception as exc:  # network-level failure
        sys.exit(f"error: request failed: {exc}")


def parse_json_field(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def summarize_market(m: dict) -> dict:
    outcomes = parse_json_field(m.get("outcomes"))
    prices = parse_json_field(m.get("outcomePrices"))
    return {"id": m.get("id"), "conditionId": m.get("conditionId"),
            "slug": m.get("slug"), "question": m.get("question"),
            "outcomes": outcomes, "outcomePrices": prices,
            "bestBid": m.get("bestBid"), "bestAsk": m.get("bestAsk"),
            "lastTradePrice": m.get("lastTradePrice"),
            "spread": m.get("spread"),
            "oneDayPriceChange": m.get("oneDayPriceChange"),
            "volume24hr": m.get("volume24hr"), "liquidity": m.get("liquidity"),
            "active": m.get("active"), "closed": m.get("closed"),
            "clobTokenIds": parse_json_field(m.get("clobTokenIds")),
            "endDate": m.get("endDate")}


def cmd_markets(args):
    if args.search:
        params = urllib.parse.urlencode(
            {"q": args.search, "limit_per_type": args.limit})
        result = get(f"{GAMMA_BASE}/public-search?{params}")
        found = result.get("markets", []) if isinstance(result, dict) else []
        out = [summarize_market(m) for m in found if isinstance(m, dict)]
    else:
        params = urllib.parse.urlencode({"limit": args.limit})
        if args.active:
            params += "&active=true"
        if args.order:
            params += "&order=" + urllib.parse.quote(args.order)
        result = get(f"{GAMMA_BASE}/markets?{params}")
        markets = result if isinstance(result, list) else []
        out = [summarize_market(m) for m in markets]
    print(json.dumps(out[:args.limit], indent=2))


def cmd_market_get(args):
    if args.slug:
        market = get(f"{GAMMA_BASE}/markets/slug/{args.slug}")
        m = market[0] if isinstance(market, list) and market else market
    else:
        market = get(f"{GAMMA_BASE}/markets/{args.condition_id}")
        m = market
    if isinstance(m, dict):
        m = dict(m)
        m["outcomes"] = parse_json_field(m.get("outcomes"))
        m["outcomePrices"] = parse_json_field(m.get("outcomePrices"))
        m["clobTokenIds"] = parse_json_field(m.get("clobTokenIds"))
    print(json.dumps(m, indent=2))


def cmd_prices(args):
    params = urllib.parse.urlencode({"interval": args.interval})
    history = get(f"{GAMMA_BASE}/markets/{args.condition_id}/prices?{params}")
    print(json.dumps(history, indent=2))


def cmd_orderbook(args):
    params = urllib.parse.urlencode({"token_id": args.token_id})
    book = get(f"{CLOB_BASE}/book?{params}")
    bids = (book.get("bids") or [])[:10]
    asks = (book.get("asks") or [])[:10]
    print(json.dumps({"token_id": args.token_id, "bids": bids, "asks": asks,
                      "note": "public CLOB snapshot, top 10 levels each "
                              "side"}, indent=2))


def cmd_events(args):
    if args.slug:
        events = get(f"{GAMMA_BASE}/events/slug/{args.slug}")
        events = [events] if isinstance(events, dict) else events
    else:
        params = {"limit": args.limit}
        if args.active:
            params["active"] = "true"
        if args.closed:
            params["closed"] = "true"
        events = get(f"{GAMMA_BASE}/events?"
                     f"{urllib.parse.urlencode(params)}")
    out = []
    for e in events if isinstance(events, list) else []:
        markets = e.get("markets") or []
        out.append({"id": e.get("id"), "slug": e.get("slug"),
                    "title": e.get("title"),
                    "active": e.get("active"), "closed": e.get("closed"),
                    "volume24hr": e.get("volume24hr"),
                    "market_count": len(markets),
                    "markets": [summarize_market(m) for m in markets[:5]]})
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Polymarket Gamma API CLI, read-only (muse-connectors)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("markets", help="list or search markets")
    p.add_argument("--search", default=None,
                   help="search query (uses public-search)")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--active", action="store_true",
                   help="only active markets (list mode)")
    p.add_argument("--order", default=None,
                   help="sort field, e.g. volume24hr (list mode)")
    p.set_defaults(func=cmd_markets)

    p = sub.add_parser("market-get", help="retrieve one market")
    p.add_argument("--condition-id", default=None)
    p.add_argument("--slug", default=None)
    p.set_defaults(func=cmd_market_get)

    p = sub.add_parser("prices", help="price history for a market")
    p.add_argument("--condition-id", required=True)
    p.add_argument("--interval", default="1d",
                   help="e.g. 1h, 6h, 1d, 1w, max")
    p.set_defaults(func=cmd_prices)

    p = sub.add_parser("orderbook", help="public order-book snapshot")
    p.add_argument("--token-id", required=True,
                   help="clob token id from market-get (Yes or No token)")
    p.set_defaults(func=cmd_orderbook)

    p = sub.add_parser("events", help="list or fetch events")
    p.add_argument("--slug", default=None,
                   help="fetch one event by slug")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--active", action="store_true")
    p.add_argument("--closed", action="store_true")
    p.set_defaults(func=cmd_events)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
