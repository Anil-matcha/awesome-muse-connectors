---
name: "xai"
description: "Query Grok chat completions and list available Grok models through the xAI API. Trigger phrases: xai, grok, chat with grok, grok model."
metadata: { "includeInPrompt": true }
tagline: "Query Grok chat completions and list available Grok models through xAI's OpenAI-compatible API, with per-call token usage surfaced so cost is always visible."
catalog_auth: "API key (per-user)"
catalog_hosts: ["api.x.ai"]
---

# xAI (Grok)

## Purpose
Send chat completions to Grok and list the Grok models available to your API key, through xAI's OpenAI-compatible REST API. Reach for this when the user wants a Grok answer, a comparison against Grok, or to see which Grok models their key can use.

## Tooling
All commands go through `bin/xai.py`:

```bash
bin/xai.py auth                                              # verify the API key
bin/xai.py models                                            # list available Grok models
bin/xai.py chat --model grok-4.6 --message "Summarize this:" # one completion (spends tokens)
bin/xai.py chat --message "Explain caching in one paragraph" \
    --system "You are a precise technical writer." \
    --temperature 0.7 --max-tokens 500                        # with options
```

`chat` takes `--message` (or `--prompt` as an alias; one is required), plus optional `--model` (default `grok-4.6`), `--system`, `--temperature`, and `--max-tokens`. Every completion prints the response text plus its token usage, so the cost is always visible.

## Auth
- Provider id: `xai` (credential is collected as `custom.xai`)
- Collection: API key (xAI console > API keys; keys start with `xai-`) via the secure credential flow (`credentials.request_api_access`)
- Auth scheme: `Authorization: Bearer <api key>` on every request
- Allowed hosts: `api.x.ai`
- Status check: `bin/xai.py auth`

## Install
Copy, paste to your Muse:

```
Install this connector: https://raw.githubusercontent.com/bluman1/muse-connectors/main/connectors/xai/SKILL.md
You are Muse. Fetch the URL above: it is a connector skill's SKILL.md.
1. Read its `## Files` manifest and download every listed file from the same directory (replace SKILL.md in the URL with each relative path).
2. Save them under ~/workspace/skills/xai/, preserving paths. Compile any bin/*.py with python3 -m py_compile.
3. Follow the skill's `## Auth` section: connect my account via your secure credential flow (credentials.request_api_access) for the provider id it names.
4. Run the skill's status check and report what the connector can now do.
Never ask me for raw API keys or secrets in chat.
```

## Operating Rules
1. **Completions spend real money.** xAI bills per token (roughly $2.00/1M input and $6.00/1M output for the flagship at the time this was written). Every `chat` prints how many tokens the call used, so the cost is visible. A single ordinary completion needs no confirmation gate, but surface the cost and confirm with the user before running large or repeated generations.
2. **Model ids move fast.** The CLI defaults to `grok-4.6`. That is the flagship named on xAI's docs page (last updated 2026-08-21). Prefer the live `models` output over this file when picking a model; a stale id produces an API error you can act on.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/xai.py`). Do not print, log, or transmit the API key.
4. Honesty flags (unverified while building this connector): the default model id `grok-4.6` was confirmed on docs.x.ai (last updated 2026-08-21) but xAI renames models often, so treat it as provisional; the `/v1/chat/completions` and `/v1/models` paths were confirmed in xAI's OpenAI-compatible docs but not live-tested. There is no usage or balance endpoint that works with a standard API key: `GET /v1/api-key` returns info about the calling key only. Real billing and usage live on xAI's separate Management API (`management-api.x.ai`), which requires a Management key plus a team id, and inference API keys are rejected there, so this connector ships no `usage` command. This connector has not been live-tested end-to-end.

## Files
- SKILL.md
- bin/xai.py

## Maturity
Draft: written from xAI's public docs (docs.x.ai, last checked 2026-09-16); not yet live-tested end-to-end.
