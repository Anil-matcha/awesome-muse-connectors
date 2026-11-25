---
name: "telegram"
description: "Send and read Telegram messages through your bot: bot info, send messages, read updates. Trigger phrases: telegram, telegram bot, send a telegram message."
metadata: { "includeInPrompt": true }
tagline: "Send messages and read updates through your own Telegram bot. Bots can't message users who haven't started them first."
catalog_auth: "Telegram bot token from @BotFather (per-user, single token)"
catalog_hosts: ["api.telegram.org"]
---

# Telegram

## Purpose
Interact with Telegram through the user's own bot: check bot identity, send messages to chats, and read recent updates (incoming messages). Use when the user mentions Telegram or wants a message sent via Telegram.

## Tooling
All commands go through `bin/telegram.py`:

```bash
bin/telegram.py me                                  # bot identity (getMe)
bin/telegram.py send --chat-id 123456789 --text "hi"  # send a message
bin/telegram.py updates                             # recent incoming updates (limit 20)
```

Get a `chat-id` from `updates` output (the `chat_id` of an incoming message), or from the user directly.

## Auth
- Provider id: `telegram` (credential is collected as `custom.telegram`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`): the bot token from @BotFather, pasted once into the hosted form
- Allowed hosts: `api.telegram.org`
- Auth mechanism: the token travels as a URL path segment (`https://api.telegram.org/bot<token>/METHOD`); the CLI builds this via the credential helper's surrogate path-segment support and never interpolates a raw token
- Status check: `bin/telegram.py me` (must return bot `id` and `username`)

## Operating Rules
1. `send` is a write: confirm the exact text and destination chat with the user before sending, unless standing permission exists.
2. Reading (`me`, `updates`) needs no confirmation.
3. Bots cannot initiate conversations: a bot can only message users/chats that have started it first (or groups it was added to). If `send` returns "chat not found", tell the user to message the bot first.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/telegram.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/telegram.py

## Maturity
🧪 Draft: written from Telegram's public Bot API docs; not yet live-tested end-to-end.
