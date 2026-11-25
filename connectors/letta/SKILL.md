---
name: "letta"
description: "Work with Letta agent memory: list agents, read core-memory blocks, list or add archival passages, create blocks, message an agent to record memory. Trigger phrases: letta, agent memory, core memory."
metadata: { "includeInPrompt": true }
tagline: "Work with Letta agent memory: list agents, read core-memory blocks, list or add archival passages, create blocks, message an agent to record memory."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.letta.com"]
---

# Letta

## Purpose
Use Letta's agent-shaped memory: list the user's agents (memory lives on a per-user "memory agent"), read core-memory blocks (persona, preferences), list or add long-term archival passages, create standalone memory blocks, and message an agent so it records or updates memory itself. Use when the user mentions Letta or wants agent-held persistent memory.

## Tooling
All commands go through `bin/letta.py`:

```bash
bin/letta.py auth                                            # verify the API key
bin/letta.py agents --limit 10                              # list agents
bin/letta.py core-memory --agent ag_abc123                  # read core-memory blocks
bin/letta.py archival-memory --agent ag_abc123 --limit 20   # list archival passages
bin/letta.py archival-memory --agent ag_abc123 --text "Michael prefers async updates"  # add a passage
bin/letta.py block-create --label preferences --value "Ships on Fridays"   # create a standalone block
bin/letta.py message --agent ag_abc123 --message "Remember that we use ISO dates"      # let the agent record it
```

List calls are cursor-paginated (`--after` / `--before`). Use `agents` first to resolve the agent ID.

## Auth
- Provider id: `letta` (credential is collected as `custom.letta`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); minted at app.letta.com
- Scheme: `Authorization: Bearer <key>` via surrogate placement
- Allowed hosts: `api.letta.com`
- Status check: `bin/letta.py auth` (must return `"ok": true`)

## Operating Rules
1. `archival-memory --text`, `block-create`, and `message` are writes: confirm with the user before running them, unless standing permission exists. Say which agent the write targets.
2. Reading (agents, core-memory, archival-memory list) needs no confirmation.
3. Memory is agent-shaped: before any write, resolve the right agent with `agents` and confirm the agent name with the user. This connector does not provision agents on its own.
4. Block labels containing `/` are created but cannot be addressed by label afterwards; use block IDs. Keep labels simple (letters, digits, underscores).
5. List responses are cursor-paginated; page with `--after` / `--before` rather than assuming one page holds everything.
6. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/letta.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/letta.py

## Maturity
🧪 Draft: written from Letta's public API docs; not yet live-tested end-to-end.
