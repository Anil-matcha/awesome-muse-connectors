---
name: "deepseek"
description: "Use DeepSeek's chat API: list models, run chat completions, check account balance. Trigger phrases: deepseek, deepseek chat, deepseek api."
metadata: { "includeInPrompt": true }
tagline: "Chat with DeepSeek's models and check account balance: OpenAI-compatible chat completions with thinking mode, model listing, and balance lookup via the official API."
catalog_auth: "API key (per-user)"
catalog_hosts: ["api.deepseek.com"]
---

# DeepSeek

## Purpose
Call the DeepSeek API from Muse: list the currently available models, run OpenAI-compatible chat completions (with thinking mode and sampling controls), and check the account balance. Reach for this when the user wants an answer from a DeepSeek model or wants to inspect their DeepSeek account.

## Tooling
All commands go through `bin/deepseek.py`:

```bash
bin/deepseek.py auth                                              # verify the API key
bin/deepseek.py models                                            # list available models
bin/deepseek.py chat --message "Explain recursion in one sentence" \
    --model deepseek-flash                                        # chat completion (SPENDS)
bin/deepseek.py chat --message "Solve: 2x+5=17" \
    --model deepseek-v4-pro --system "Show your work." \
    --temperature 0.2 --max-tokens 500                             # with options
bin/deepseek.py balance                                           # account balance
```

The chat command prints the reply plus token usage and a cost note. Thinking-mode
models also return `reasoning_content` when the API provides it.

## Auth
- Provider id: `deepseek` (credential is collected as `custom.deepseek`)
- Collection: API key (platform.deepseek.com > API keys) via the secure credential flow (`credentials.request_api_access`)
- Auth scheme: `Authorization: Bearer <api key>` on every request
- Allowed hosts: `api.deepseek.com`
- Status check: `bin/deepseek.py auth`

## Operating Rules
1. **Chat completions cost real money.** Every `chat` call consumes paid DeepSeek tokens. Each response reports usage; check `balance` first when the budget is unclear. `models` and `balance` are read-only and cost nothing.
2. **Default to `deepseek-flash`** unless the user asks for the stronger model; it is the cheaper of the two documented models.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/deepseek.py`). Do not print, log, or transmit the API key.
4. **Honesty flags (unverified while building this connector):** the connector was written from DeepSeek's public API docs and never run against a live account, so the model ids (`deepseek-flash`, `deepseek-v4-pro`) and endpoint paths were current in the docs but could drift. Some integration docs show a `/v1`-prefixed path (e.g. `/v1/chat/completions`); the canonical API reference documents the unprefixed forms (`/chat/completions`, `/models`, `/user/balance`), which this CLI uses. The balance response shape (`is_available` plus `balance_infos` with `currency` / `total_balance` / `granted_balance` / `topped_up_balance`) matches the docs but was not live-verified; the CLI passes the API's own response through untouched. Older ids (`deepseek-chat`, `deepseek-reasoner`) no longer appear in the docs' model enum; they may still work as aliases, but the CLI surfaces the API's own error if they do not.

## Files
- SKILL.md
- bin/deepseek.py

## Install
Copy, paste to your Muse:

```
Install this connector: https://raw.githubusercontent.com/bluman1/muse-connectors/main/connectors/deepseek/SKILL.md
You are Muse. Fetch the URL above: it is a connector skill's SKILL.md.
1. Read its `## Files` manifest and download every listed file from the same directory (replace SKILL.md in the URL with each relative path).
2. Save them under ~/workspace/skills/deepseek/, preserving paths. Compile any bin/*.py with python3 -m py_compile.
3. Follow the skill's `## Auth` section: connect my account via your secure credential flow (credentials.request_api_access) for the provider id it names.
4. Run the skill's status check and report what the connector can now do.
Never ask me for raw API keys or secrets in chat.
```

## Maturity
Draft: written from DeepSeek's public API docs (checked 2026-09-16); not yet live-tested end-to-end.
