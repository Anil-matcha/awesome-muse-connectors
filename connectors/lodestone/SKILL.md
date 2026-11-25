---
name: "lodestone"
description: "Use Lodestone (lodestone.studiocorsair.com) as one MCP connector for Meta Ads, Instagram insights, Google Analytics 4, email, Telegram, Typefully, and image/video generation. Trigger phrases: lodestone, meta ads, ad campaign insights, instagram insights, ga4 report, google analytics report, send email, telegram message, typefully post, generate image, generate video."
metadata: { "includeInPrompt": true }
tagline: "One key for Meta Ads, Instagram insights, GA4, email, Telegram, Typefully, and image/video generation."
catalog_auth: "API key (per-user Lodestone connector key)"
catalog_hosts: ["lodestone.studiocorsair.com"]
---

# Lodestone

## Purpose
Lodestone is a hosted MCP server that puts several services behind one per-user key. Muse should reach for it when a task needs the user's own Meta Ads account, Instagram account insights, Google Analytics 4 reports, email, a Telegram bot, a Typefully queue, or AI image and video generation.

The connector uses the `muse-directory` connection origin, which exposes 39 tools: 24 read-only and 15 that create, change, spend, or send. Each service beyond the key (Google Analytics, Meta Ads, Typefully, and so on) is connected by the user in their Lodestone dashboard; a tool for an unconnected service replies with the dashboard link instead of failing silently.

Source: the server's own `tools/list` response (MCP Streamable HTTP, JSON-RPC), checked 2026-10-09. Lodestone's MCP OAuth flow did not complete from Muse in testing, so this connector uses the API key path (`Authorization: Bearer`).

Disclosure: the contributor built and operates Lodestone.

## Tooling
All commands go through `bin/lodestone.py` (Python standard library only).

```bash
# Verify the key and reach the server (prints the tool count)
bin/lodestone.py auth

# List every tool; WRITE marks anything that is not read-only
bin/lodestone.py tools

# Call a read-only tool
bin/lodestone.py call typefully_whoami
bin/lodestone.py call meta_ads_list_accounts
bin/lodestone.py call ga4_run_report --args '{"property_id":"123456789"}'

# Call a tool that creates, changes, spends, or sends (needs explicit user approval first)
bin/lodestone.py call email_send --args '{"to":"a@example.com","subject":"Hi","body":"Hello"}' --confirm
```

Run `bin/lodestone.py tools` first. Tool argument names come from the server; `call` forwards `--args` as the JSON `arguments` object unchanged.

## Auth
- Provider id: `lodestone` (credential is collected as `custom.lodestone`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`). The user copies their connector key from their Lodestone dashboard. For local use, export it as `LODESTONE_KEY`. The key is never accepted as a command-line argument.
- Required scopes: none; the key identifies the user's Lodestone account
- Allowed hosts: `lodestone.studiocorsair.com`
- Status check: `bin/lodestone.py auth`

## Operating Rules
1. `call` refuses any tool whose server annotations are not `readOnlyHint: true` unless `--confirm` is passed. Tools that need it include `email_send`, `telegram_send_message`, `typefully_post`, every `meta_ads_create_*` / `meta_ads_update_*` / `meta_ads_set_status` / `meta_ads_boost_post`, and the five `generate_*` media tools.
2. Before using `--confirm`, show the user the exact tool and arguments and wait for approval. Never pass `--confirm` on your own initiative.
3. Meta Ads writes can spend real money and email, Telegram, and Typefully writes reach real people. Prefer drafts and read-only calls.
4. The key is a secret. Never print, log, or commit it.
5. Only `lodestone.studiocorsair.com` is contacted.

## Files
- SKILL.md
- bin/lodestone.py

## Maturity
✅ Live-tested against the real server on 2026-10-09 with a real connector key: `auth` (39 tools), `tools` (24 read, 15 write), `call` on read-only tools, `call` refusing `email_send` without `--confirm`, unknown tool, bad key (HTTP 401), and missing key. The `--confirm` write path was deliberately not run live because every write tool sends, spends, or publishes.
