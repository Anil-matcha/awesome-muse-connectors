---
name: "front"
description: "Work with Front: list inboxes and conversations, reply to conversations, assign teammates, add tags. Writes need --confirm. Trigger phrases: front, front inbox, shared inbox, support inbox."
metadata: { "includeInPrompt": true }
tagline: "Read your Front shared inbox, and reply, assign teammates, and add tags on conversations (writes need --confirm)."
catalog_auth: "Front API token (per-user, Front Settings \u2192 API)"
catalog_hosts: ["api2.frontapp.com"]
---

# Front

## Purpose
Work with the user's Front (shared-inbox) account: list inboxes (`inboxes`: name, address), list conversations in an inbox (`conversations`: subject, status), list teammates (`teammates`: id, name, email), and write: reply to a conversation (`reply`), assign a teammate (`assign`), and add tags (`tag`). The API token needs the `messages:send` scope for replies and `conversations:write` for assign/tag.

## Tooling
All commands go through `bin/front.py`:

```bash
bin/front.py inboxes                        # list inboxes (name, address)
bin/front.py conversations --inbox inb_123  # recent conversations (subject, status)
bin/front.py teammates                      # teammates (id, name, email)

# writes: every one requires the exact --confirm string the CLI prints
bin/front.py reply --conversation cnv_123 --to customer@example.com --body "<p>Thanks for writing in.</p>"
bin/front.py reply --conversation cnv_123 --to customer@example.com --body "<p>Update:</p>" --subject "Re: billing question" --author-id tea_456
bin/front.py assign --conversation cnv_123 --teammate tea_456
bin/front.py assign --conversation cnv_123 --unassign
bin/front.py tag --conversation cnv_123 --tags tag_1,tag_2
```

Use `inboxes` first to resolve an inbox name to its id, and `teammates` to resolve a person to their `tea_*` id before `assign`. `--to` takes recipient handles (usually the contact's email). `--body` is HTML on email channels.

## Auth
- Provider id: `front` (credential is collected as `custom.front`)
- Collection: API token via the secure credential flow (`credentials.request_api_access`): create one in Front → Settings → API (needs API access enabled)
- Connect placement: `bearer_header`
- Allowed hosts: `api2.frontapp.com`
- Status check: `bin/front.py inboxes` (a successful list proves the token works)

## Operating Rules
1. Reads need no confirmation. Every write (`reply`, `assign`, `tag`) requires the exact-match `--confirm` string: run the command once without it, read the refused string from the output, confirm the effect with the user, then re-run with it.
2. Replies send real messages to real people: show the user the exact `--body` before confirming, and double-check the `--conversation` id and `--to` recipients.
3. Front's conversation-update API replaces all tags, so `tag` first reads the conversation's current tags and merges the new ones in (best-effort read, untested live). To set an exact tag list instead, the PATCH body is documented in `bin/front.py`.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/front.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/front.py

## Maturity
🧪 Draft: written from Front's public Core API docs; not yet live-tested end-to-end. The write endpoints (`reply`, `assign`, `tag`) are doc-built only: paths and bodies follow the public dev-frontapp.com reference pages but have never been run against a real workspace.
