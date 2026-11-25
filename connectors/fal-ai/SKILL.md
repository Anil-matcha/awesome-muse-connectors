---
name: "fal-ai"
description: "Generate media with fal.ai: images, video, audio, music on one key. Submit jobs to 100s of models, poll status, fetch results, upload files. Trigger phrases: fal.ai, fal, run a fal model, flux pro on fal, kling video via fal."
metadata: { "includeInPrompt": true }
tagline: "Generate media with fal.ai: images, video, audio, music on one key. Submit jobs to 100s of models, poll status, fetch results, upload files."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["fal.run", "queue.fal.run", "rest.alpha.fal.ai"]
---

# fal.ai

## Purpose
Run fal.ai's model marketplace: one API key unlocks hundreds of models spanning images, video, audio, voice, music (FLUX, Veo, Kling, Luma, Minimax, Wan, Stable Audio). Use when Michael asks for AI image/video/audio generation or names a specific fal model. There is also an official MCP server at https://mcp.fal.ai/mcp if an MCP route is ever preferred.

## Tooling
All commands go through `bin/fal-ai.py`:

```bash
bin/fal-ai.py auth                                                        # verify the API key (free)
bin/fal-ai.py models                                                      # list the model catalog
bin/fal-ai.py run --model fal-ai/flux-2-pro --params '{"prompt": "a lighthouse at dusk"}'   # submit a job
bin/fal-ai.py status --model fal-ai/flux-2-pro --id <request_id>           # poll the job
bin/fal-ai.py result --model fal-ai/flux-2-pro --id <request_id>           # fetch the finished result
bin/fal-ai.py upload --file ./input.png                                   # upload a local file to fal's CDN
```

`run` takes any model slug (e.g. `fal-ai/kling-video/v2.5-turbo/text-to-video`, `fal-ai/veo3.1/fast`) and model input as a JSON object via `--params`. It prints a `request_id`; poll with `status` until the job is done, then fetch with `result`.

## Auth
- Provider id: `fal-ai` (credential is collected as `custom.fal-ai`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created at fal.ai/dashboard/keys
- Allowed hosts: `fal.run`, `queue.fal.run`, `rest.alpha.fal.ai`
- Status check: `bin/fal-ai.py auth` (must return `"ok": true`). The key is sent verbatim as `Authorization: Key <key>` on REST calls.

## Operating Rules
1. Every `run` spends prepaid balance (pay-per-use, priced per model). Confirm with Michael before submitting, stating the model slug and the cost if known. There is no free tier for inference.
2. Failed jobs do not charge; only successful runs spend balance.
3. Jobs are async: submit, then poll `status` with backoff until done, then call `result`.
4. Generated file URLs expire. Download promptly and never treat the URL as the finished artifact.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/fal-ai.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/fal-ai.py

## Maturity
🧪 Draft: written from fal.ai's public docs via the research dossier; not yet live-tested end-to-end.
