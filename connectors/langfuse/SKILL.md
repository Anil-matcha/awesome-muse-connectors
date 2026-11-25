---
name: "langfuse"
description: "Read and write Langfuse: browse traces and observations, list prompts and datasets, score traces, add dataset items. Trigger phrases: langfuse, llm observability."
metadata: { "includeInPrompt": true }
tagline: "Query traces and observations, manage prompts and scores."
catalog_auth: "Public+secret key pair (per-project; host declared at connect time)"
catalog_hosts: ["cloud.langfuse.com", "us.cloud.langfuse.com"]
---

# Langfuse

## Purpose
Read and write the user's Langfuse LLM observability data: browse traces and observations, list prompts and datasets, score traces, and add dataset items. Use when the user mentions Langfuse or LLM tracing and evaluation.

## Tooling
All commands go through `bin/langfuse.py`. Every command takes an optional `--host` (default `https://cloud.langfuse.com`; use `https://us.cloud.langfuse.com` for US-hosted projects or your self-hosted URL):

```bash
bin/langfuse.py auth                                            # verify the credential
bin/langfuse.py traces                                          # list traces
bin/langfuse.py traces --session-id abc123                      # traces for one session
bin/langfuse.py observations                                    # list observations
bin/langfuse.py prompts                                         # list prompts
bin/langfuse.py prompts --name my-prompt                        # one prompt's details
bin/langfuse.py score --trace-id tr_abc --name quality --value 0.9  # score a trace (confirm first)
bin/langfuse.py datasets                                        # list datasets
bin/langfuse.py dataset-item --dataset-name evals --input-json '{"q":"..."}'  # add a dataset item (confirm first)
```

## Auth
- Provider id: `langfuse` (credential is collected as `custom.langfuse`)
- Collection: via the secure credential flow (`credentials.request_api_access`). The credential stores ONE combined value in the format `public_key:secret_key` (e.g. `pk-lf-...:sk-lf-...`), as issued in Langfuse under Settings > API keys. The CLI splits on the first colon into username (public key) and password (secret key) and sends them as HTTP Basic auth (`Authorization: Basic base64(pk:sk)`). Store the combined value exactly once, with exactly one colon separator.
- Allowed hosts: `cloud.langfuse.com`, `us.cloud.langfuse.com`, or your self-hosted Langfuse host (declared at connect time via `--host`)
- Status check: `bin/langfuse.py auth` (must return `"ok": true`)

## Operating Rules
1. `score` and `dataset-item` are writes: confirm the trace or dataset and the values with the user before running, unless standing permission exists.
2. Reading (traces, observations, prompts, datasets) needs no confirmation.
3. Ingested data can lag ~15-30 seconds behind a run; a missing trace may just need a moment.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/langfuse.py

## Maturity
🧪 Draft: written from Langfuse's public API docs; not yet live-tested end-to-end.
