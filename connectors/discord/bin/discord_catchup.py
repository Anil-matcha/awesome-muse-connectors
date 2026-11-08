"""Read-only catch-up commands for the discord connector: `mentions` and `digest`.

They answer "what happened in this server while I was away" and "who mentioned
me since <time>". Both only ever read. They use discord.py's `request()` for
HTTP (same credential, host allowlist and auth header) and add what a
multi-channel scan needs on top:

  * one GET each for /users/@me, the guild, the bot's member record, the
    channel list and (unless --no-threads) the active threads;
  * channels the bot cannot read (computed from roles and overwrites) are
    skipped without a request, so a scan does not rack up 403s;
  * channels whose last_message_id is older than the window are skipped
    without a request;
  * the rest are read newest-first, 100 per page, stopping at the window start
    or at --per-channel, most recently active channel first, at most
    --max-channels channels;
  * 429 responses are retried after the API's retry_after (bounded), and
    --max-requests caps the total number of calls per invocation.

Scope: a bot sees only servers it was invited to and only channels where it
has View Channel and Read Message History. It cannot read anyone's personal
DMs, so these commands scan server channels and active threads only.
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

# Set by register(): the discord.py module (passed in, never imported by name,
# so running discord.py as __main__ keeps a single copy of its classes).
core = None

DEFAULT_MAX_CHANNELS = 60
DEFAULT_MAX_REQUESTS = 250
MAX_429_RETRIES = 3
MAX_WAIT_SECONDS = 60.0

DISCORD_EPOCH_MS = 1420070400000
SNOWFLAKE_RE = re.compile(r"^[0-9]{15,22}$")

CHANNEL_TYPES = {
    0: "text", 2: "voice", 4: "category", 5: "announcement",
    10: "announcement_thread", 11: "public_thread", 12: "private_thread",
    13: "stage", 15: "forum", 16: "media",
}
# Guild channel types that hold a readable message history.
MESSAGE_CHANNEL_TYPES = {0, 2, 5, 10, 11, 12, 13}
THREAD_TYPES = {10, 11, 12}

PERM_ADMINISTRATOR = 1 << 3
PERM_VIEW_CHANNEL = 1 << 10
PERM_READ_MESSAGE_HISTORY = 1 << 16
PERM_ALL = (1 << 64) - 1


class BudgetExceeded(Exception):
    pass


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def fail(message: str):
    sys.exit(f"error: {message}")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def snowflake_id(value: str, what: str) -> str:
    value = (value or "").strip()
    if not SNOWFLAKE_RE.match(value):
        fail(f"{what} must be a numeric Discord ID (snowflake), got {value!r}")
    return value


def snowflake_at(moment: datetime) -> int:
    """Smallest snowflake that could have been created at `moment`."""
    ms = int(moment.timestamp() * 1000) - DISCORD_EPOCH_MS
    return max(ms, 0) << 22


def parse_since(text: str) -> datetime:
    raw = (text or "").strip()
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        fail(f"--since must be ISO 8601, such as 2026-01-01T18:00:00Z, got {raw!r}")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def snippet(message: dict, width: int = 200) -> str:
    text = " ".join((message.get("content") or "").split())
    extras = []
    if message.get("attachments"):
        extras.append(f"[{len(message['attachments'])} attachment(s)]")
    if message.get("embeds"):
        extras.append("[embed]")
    if message.get("sticker_items"):
        extras.append("[sticker]")
    if message.get("poll"):
        extras.append("[poll]")
    if extras:
        text = (text + " " + " ".join(extras)).strip()
    if len(text) > width:
        text = text[: width - 3].rstrip() + "..."
    return text


def author_of(message: dict) -> dict:
    a = message.get("author") or {}
    return {"id": a.get("id"),
            "display_name": a.get("global_name") or a.get("username"),
            "bot": bool(a.get("bot"))}


def jump_url(guild_id, channel_id, message_id=None) -> str:
    url = f"https://discord.com/channels/{guild_id}/{channel_id}"
    return f"{url}/{message_id}" if message_id else url


def content_intent_warning(raw_messages) -> str | None:
    """Without the Message Content intent, other users' content comes back empty."""
    human = [m for m in raw_messages
             if not (m.get("author") or {}).get("bot") and m.get("type") in (0, 19)]
    empty = [m for m in human
             if not m.get("content") and not m.get("attachments") and not m.get("embeds")
             and not m.get("sticker_items") and not m.get("poll")]
    if len(empty) >= 3 and len(empty) >= 0.8 * len(human):
        return ("most messages came back with empty content. The bot's Message Content "
                "intent is probably off. Enable it in the Discord Developer Portal under "
                "Bot > Privileged Gateway Intents.")
    return None


def base_permissions(guild: dict, role_ids, user_id: str) -> int:
    if guild.get("owner_id") == user_id:
        return PERM_ALL
    roles = {r["id"]: r for r in guild.get("roles") or []}
    perms = int((roles.get(guild["id"]) or {}).get("permissions", 0))
    for rid in role_ids:
        perms |= int((roles.get(rid) or {}).get("permissions", 0))
    return PERM_ALL if perms & PERM_ADMINISTRATOR else perms


def channel_permissions(base: int, channel: dict, guild_id: str, role_ids,
                        user_id: str) -> int:
    if base & PERM_ADMINISTRATOR:
        return PERM_ALL
    perms = base
    overwrites = {o["id"]: o for o in channel.get("permission_overwrites") or []}
    everyone = overwrites.get(guild_id)
    if everyone:
        perms &= ~int(everyone.get("deny", 0))
        perms |= int(everyone.get("allow", 0))
    allow = deny = 0
    for rid in role_ids:
        ow = overwrites.get(rid)
        if ow and int(ow.get("type", 0)) == 0:
            allow |= int(ow.get("allow", 0))
            deny |= int(ow.get("deny", 0))
    perms &= ~deny
    perms |= allow
    ow = overwrites.get(user_id)
    if ow and int(ow.get("type", 1)) == 1:
        perms &= ~int(ow.get("deny", 0))
        perms |= int(ow.get("allow", 0))
    return perms


# --------------------------------------------------------------------------
# Scan client: core.request() plus 429 handling and a request budget
# --------------------------------------------------------------------------

class Scanner:
    def __init__(self, max_requests: int = DEFAULT_MAX_REQUESTS, sleep=time.sleep):
        self.max_requests = max_requests
        self.sleep = sleep
        self.requests = 0
        self.waited = 0.0
        self._me = None

    def get(self, path: str, params: dict | None = None):
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        tries = 0
        while True:
            if self.requests >= self.max_requests:
                raise BudgetExceeded(
                    f"request budget of {self.max_requests} reached for this invocation")
            self.requests += 1
            try:
                return core.request("GET", path, params=params or None)
            except core.ApiError as exc:
                if exc.status != 429:
                    raise
                wait = _retry_after(exc)
                if wait > MAX_WAIT_SECONDS or tries >= MAX_429_RETRIES:
                    fail(f"rate limited by discord on {path}; retry_after {wait:.1f}s. "
                         "Wait at least that long before trying again.")
                tries += 1
                print(f"notice: rate limited, waiting {wait:.2f}s as the API asked",
                      file=sys.stderr)
                self.waited += wait
                self.sleep(wait + 0.05)

    def me(self) -> dict:
        if self._me is None:
            self._me = self.get("/users/@me")
        return self._me

    def history(self, channel_id: str, limit: int, stop_below: int):
        """Newest-first messages at or after snowflake `stop_below`, up to `limit`.

        Returns (messages, complete); complete is False when `limit` cut it short.
        """
        out, before = [], None
        while len(out) < limit:
            want = min(100, limit - len(out))
            page = self.get(f"/channels/{channel_id}/messages",
                            {"limit": want, "before": before}) or []
            kept = [m for m in page if int(m["id"]) >= stop_below]
            out.extend(kept)
            if len(kept) < len(page) or len(page) < want:
                return out, True
            before = page[-1]["id"]
        return out[:limit], False

    def readable_map(self, guild: dict, channels: list) -> dict:
        """channel id -> True/False for View Channel + Read Message History."""
        bot_id = self.me()["id"]
        member = self.get(f"/guilds/{guild['id']}/members/{bot_id}") or {}
        role_ids = list(member.get("roles") or [])
        base = base_permissions(guild, role_ids, bot_id)
        by_id = {c["id"]: c for c in channels}
        need = PERM_VIEW_CHANNEL | PERM_READ_MESSAGE_HISTORY
        result = {}
        for ch in channels:
            source = ch
            if ch.get("type") in THREAD_TYPES and ch.get("parent_id") in by_id:
                source = by_id[ch["parent_id"]]
            perms = channel_permissions(base, source, guild["id"], role_ids, bot_id)
            result[ch["id"]] = (perms & need) == need
        return result


def _retry_after(exc) -> float:
    headers = exc.headers
    candidates = [exc.body.get("retry_after")]
    if headers is not None:
        candidates += [headers.get("Retry-After"), headers.get("X-RateLimit-Reset-After")]
    for value in candidates:
        if value is None:
            continue
        try:
            return max(float(value), 0.0)
        except (TypeError, ValueError):
            continue
    return 1.0


def _api_error_text(exc) -> str:
    if exc.status is None:
        return f"request failed: {exc.message}"
    return f"HTTP {exc.status}: {exc.message}"


# --------------------------------------------------------------------------
# Guild scan
# --------------------------------------------------------------------------

class ScanResult:
    def __init__(self, guild):
        self.guild = guild
        self.channels = []          # (channel, raw newest-first messages, complete)
        self.skipped = []           # {"id", "name", "reason"}
        self.quiet = 0
        self.truncated = False
        self.warnings = []
        self.raw_all = []


def scan_guild(api: Scanner, guild_id: str, since, *, include_threads=True,
               max_channels=DEFAULT_MAX_CHANNELS, per_channel=300) -> ScanResult:
    guild = api.get(f"/guilds/{guild_id}")
    result = ScanResult(guild)
    channels = list(api.get(f"/guilds/{guild_id}/channels") or [])
    if include_threads:
        try:
            channels += (api.get(f"/guilds/{guild_id}/threads/active") or {}).get("threads", [])
        except core.ApiError as exc:
            result.warnings.append(f"active threads not listed: {_api_error_text(exc)}")
    readable = None
    try:
        readable = api.readable_map(guild, channels)
    except core.ApiError as exc:
        result.warnings.append("could not compute channel access, reading optimistically: "
                               + _api_error_text(exc))

    stop_below = snowflake_at(since)
    candidates = []
    for ch in channels:
        if ch.get("type") not in MESSAGE_CHANNEL_TYPES:
            continue
        if readable is not None and not readable.get(ch["id"], True):
            result.skipped.append({"id": ch["id"], "name": ch.get("name"),
                                   "reason": "bot lacks View Channel or Read Message History"})
            continue
        last = ch.get("last_message_id")
        if not last or int(last) < stop_below:
            result.quiet += 1
            continue
        candidates.append(ch)
    candidates.sort(key=lambda c: int(c["last_message_id"]), reverse=True)
    if len(candidates) > max_channels:
        for ch in candidates[max_channels:]:
            result.skipped.append({"id": ch["id"], "name": ch.get("name"),
                                   "reason": f"over --max-channels {max_channels}"})
        candidates = candidates[:max_channels]
        result.truncated = True

    for index, ch in enumerate(candidates):
        try:
            raw, complete = api.history(ch["id"], per_channel, stop_below)
        except BudgetExceeded as exc:
            result.truncated = True
            result.warnings.append(f"{exc}; {len(candidates) - index} channel(s) not read")
            for rest in candidates[index:]:
                result.skipped.append({"id": rest["id"], "name": rest.get("name"),
                                       "reason": "request budget reached"})
            break
        except core.ApiError as exc:
            if exc.status in (403, 404):
                result.skipped.append({"id": ch["id"], "name": ch.get("name"),
                                       "reason": f"HTTP {exc.status}"})
                continue
            raise
        if not complete:
            result.truncated = True
        result.channels.append((ch, raw, complete))
        result.raw_all.extend(raw)

    warning = content_intent_warning(result.raw_all)
    if warning:
        result.warnings.append(warning)
    return result


def mention_reasons(message: dict, user_id: str, role_ids=frozenset(),
                    include_everyone=False) -> list:
    reasons = []
    content = message.get("content") or ""
    if any((u or {}).get("id") == user_id for u in message.get("mentions") or []) or \
            re.search(rf"<@!?{re.escape(user_id)}>", content):
        reasons.append("mention")
    ref = message.get("referenced_message") or {}
    if message.get("type") == 19 and (ref.get("author") or {}).get("id") == user_id:
        reasons.append("reply")
    if role_ids and set(message.get("mention_roles") or []) & set(role_ids):
        reasons.append("role")
    if include_everyone and message.get("mention_everyone"):
        reasons.append("everyone")
    return reasons


def _hit(guild_id, channel, message, reasons) -> dict:
    author = author_of(message)
    return {"channel_id": channel["id"], "channel_name": channel.get("name"),
            "message_id": message["id"], "timestamp": message.get("timestamp"),
            "author": author["display_name"], "author_id": author["id"],
            "reasons": reasons, "snippet": snippet(message),
            "jump_url": jump_url(guild_id, channel["id"], message["id"])}


def _member_roles(api, guild_id, user_id, warnings) -> frozenset:
    try:
        member = api.get(f"/guilds/{guild_id}/members/{user_id}") or {}
        return frozenset(member.get("roles") or [])
    except core.ApiError as exc:
        warnings.append(f"role mentions not checked: {_api_error_text(exc)}")
        return frozenset()


def _window_meta(api, scan: ScanResult, since, until) -> dict:
    return {"guild": {"id": scan.guild.get("id"), "name": scan.guild.get("name")},
            "window": {"since": iso(since), "until": iso(until)},
            "skipped_channels": scan.skipped,
            "quiet_channel_count": scan.quiet,
            "truncated": scan.truncated,
            "requests_used": api.requests,
            "rate_limit_wait_seconds": round(api.waited, 2),
            "warnings": scan.warnings}


def _emit(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _check_scan_flags(args) -> None:
    if not 1 <= args.max_channels <= 500:
        fail("--max-channels must be between 1 and 500")
    if not 1 <= args.per_channel <= 2000:
        fail("--per-channel must be between 1 and 2000")
    if not 1 <= args.max_requests <= 2000:
        fail("--max-requests must be between 1 and 2000")


def _run(fn, args):
    _check_scan_flags(args)
    api = Scanner(max_requests=args.max_requests)
    try:
        _emit(fn(api, args))
    except BudgetExceeded as exc:
        fail(str(exc))
    except core.ApiError as exc:
        fail("discord " + _api_error_text(exc))


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def build_mentions(api: Scanner, args) -> dict:
    gid = snowflake_id(args.guild, "--guild")
    uid = snowflake_id(args.user_id, "--user-id")
    since = parse_since(args.since)
    until = utcnow()
    if since >= until:
        fail("--since is in the future")
    scan = scan_guild(api, gid, since, include_threads=not args.no_threads,
                      max_channels=args.max_channels, per_channel=args.per_channel)
    roles = _member_roles(api, gid, uid, scan.warnings) if args.include_roles else frozenset()
    hits = []
    for ch, raw, _complete in scan.channels:
        for m in raw:
            if (m.get("author") or {}).get("id") == uid:
                continue
            reasons = mention_reasons(m, uid, roles, args.include_everyone)
            if reasons:
                hits.append(_hit(gid, ch, m, reasons))
    hits.sort(key=lambda h: int(h["message_id"]))
    out = {"user_id": uid, "hit_count": len(hits), "hits": hits,
           "scanned_channel_count": len(scan.channels)}
    out.update(_window_meta(api, scan, since, until))
    return out


def digest_channel(guild_id, channel, raw, complete, *, user_id=None, role_ids=frozenset(),
                   snippets=3, include_bots=False) -> dict:
    chron = sorted(raw, key=lambda m: int(m["id"]))
    bot_count = sum(1 for m in chron if (m.get("author") or {}).get("bot"))
    msgs = chron if include_bots else [m for m in chron
                                       if not (m.get("author") or {}).get("bot")]
    counts, names = Counter(), {}
    for m in msgs:
        a = author_of(m)
        counts[a["id"]] += 1
        names[a["id"]] = (a["display_name"], a["bot"])
    row = {
        "channel_id": channel["id"], "name": channel.get("name"),
        "type_name": CHANNEL_TYPES.get(channel.get("type"), "other"),
        "parent_id": channel.get("parent_id"),
        "message_count": len(msgs),
        "count_is_floor": not complete,
        "bot_message_count": bot_count,
        "first_at": msgs[0].get("timestamp") if msgs else None,
        "last_at": msgs[-1].get("timestamp") if msgs else None,
        "unique_authors": len(counts),
        "top_authors": [{"id": aid, "name": names[aid][0], "bot": names[aid][1], "count": n}
                        for aid, n in sorted(counts.items(),
                                             key=lambda kv: (-kv[1], kv[0] or ""))[:5]],
        "latest": [{"message_id": m["id"], "timestamp": m.get("timestamp"),
                    "author": author_of(m)["display_name"], "snippet": snippet(m)}
                   for m in msgs[-snippets:]] if snippets else [],
        "jump_url": jump_url(guild_id, channel["id"]),
    }
    if user_id:
        hits = [_hit(guild_id, channel, m, r) for m in msgs
                if (m.get("author") or {}).get("id") != user_id
                for r in [mention_reasons(m, user_id, role_ids)] if r]
        row["mention_hit_count"] = len(hits)
        row["mention_hits"] = hits
    return row


def build_digest(api: Scanner, args) -> dict:
    gid = snowflake_id(args.guild, "--guild")
    uid = snowflake_id(args.user_id, "--user-id") if args.user_id else None
    if not 0 < args.hours <= 336:
        fail("--hours must be more than 0 and at most 336 (14 days)")
    if not 0 <= args.snippets <= 20:
        fail("--snippets must be between 0 and 20")
    until = utcnow()
    since = until - timedelta(hours=args.hours)
    scan = scan_guild(api, gid, since, include_threads=not args.no_threads,
                      max_channels=args.max_channels, per_channel=args.per_channel)
    roles = _member_roles(api, gid, uid, scan.warnings) if (uid and args.include_roles) \
        else frozenset()
    rows = [digest_channel(gid, ch, raw, complete, user_id=uid, role_ids=roles,
                           snippets=args.snippets, include_bots=args.include_bots)
            for ch, raw, complete in scan.channels]
    rows = [r for r in rows if r["message_count"] or r.get("mention_hit_count")]
    rows.sort(key=lambda r: (-r["message_count"], r["name"] or ""))
    totals = {"active_channels": len(rows),
              "messages": sum(r["message_count"] for r in rows)}
    if uid:
        totals["mention_hits"] = sum(r["mention_hit_count"] for r in rows)
    out = {"hours": args.hours, "user_id": uid, "totals": totals, "channels": rows}
    out.update(_window_meta(api, scan, since, until))
    return out


def cmd_mentions(args):
    _run(build_mentions, args)


def cmd_digest(args):
    _run(build_digest, args)


def _scan_flags(parser, per_channel_default):
    parser.add_argument("--no-threads", action="store_true", help="skip active threads")
    parser.add_argument("--max-channels", type=int, default=DEFAULT_MAX_CHANNELS,
                        help="read at most this many active channels (default %(default)s)")
    parser.add_argument("--per-channel", type=int, default=per_channel_default,
                        help="read at most this many messages per channel "
                             "(default %(default)s)")
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS,
                        help="stop after this many API calls (default %(default)s)")
    parser.add_argument("--include-roles", action="store_true",
                        help="also count @role mentions of the user's roles (1 extra request)")


def register(sub, core_module) -> None:
    global core
    core = core_module

    s = sub.add_parser("mentions", help="messages mentioning or replying to a user since a "
                                        "time, across readable server channels (read-only)")
    s.add_argument("--guild", required=True, help="server (guild) ID")
    s.add_argument("--user-id", required=True, help="the user's Discord ID (Copy User ID)")
    s.add_argument("--since", required=True, help="ISO 8601, UTC when no offset is given")
    s.add_argument("--include-everyone", action="store_true",
                   help="also count @everyone and @here")
    _scan_flags(s, 500)
    s.set_defaults(func=cmd_mentions)

    s = sub.add_parser("digest", help="per-channel activity summary for the last N hours "
                                      "(read-only)")
    s.add_argument("--guild", required=True, help="server (guild) ID")
    s.add_argument("--hours", type=float, default=24.0)
    s.add_argument("--user-id", help="add mention hits for this user ID")
    s.add_argument("--snippets", type=int, default=3,
                   help="latest messages per channel to include (default %(default)s)")
    s.add_argument("--include-bots", action="store_true",
                   help="count bot-authored messages (excluded by default)")
    _scan_flags(s, 300)
    s.set_defaults(func=cmd_digest)
