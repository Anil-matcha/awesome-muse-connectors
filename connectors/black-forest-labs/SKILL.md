---
name: "black-forest-labs"
description: "Black Forest Labs FLUX image generation: flux-2-pro and flux-2-flex text-to-image with async polling. Trigger phrases: black forest labs, BFL, flux image, flux-2-pro, flux 2 generate."
metadata: { "includeInPrompt": true }
tagline: "Black Forest Labs FLUX image generation: flux-2-pro and flux-2-flex text-to-image with async polling."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.bfl.ai", "api.eu.bfl.ai", "api.us.bfl.ai"]
---

# FLUX image API

## Purpose
Generate images with the FLUX.2 family via Black Forest Labs' official API: `flux-2-pro` for general text-to-image and native image editing, `flux-2-flex` for typography and text-heavy images. The quality bar for custom imagery in the catalog. Regional hosts exist for GDPR (`api.eu.bfl.ai`) and US (`api.us.bfl.ai`).

## Tooling
All commands go through `bin/black-forest-labs.py`:

```bash
bin/black-forest-labs.py auth                                             # verify credential setup (no spend)
bin/black-forest-labs.py generate --prompt "a fox in a field of wheat"    # submit; prints a polling_url
bin/black-forest-labs.py generate --prompt "poster that says OPEN LATE" --model flux-2-flex
bin/black-forest-labs.py generate --prompt "..." --region https://api.eu.bfl.ai
bin/black-forest-labs.py status --polling-url 'https://api.bfl.ai/v1/get_result?id=...'   # poll until Ready
bin/black-forest-labs.py result --polling-url 'https://api.bfl.ai/v1/get_result?id=...'  # fetch the result
```

`generate` returns a `polling_url`. Poll `status` with backoff; when status is `Ready`, the response carries the sample download URL. `--json` merges extra fields (width, height, seed, input images for editing) into the request.

## Auth
- Provider id: `black-forest-labs` (credential is collected as `custom.black-forest-labs`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); created at dashboard.bfl.ai
- Allowed hosts: `api.bfl.ai`, `api.eu.bfl.ai`, `api.us.bfl.ai`
- Status check: `bin/black-forest-labs.py auth` (must return `"ok": true`). The key is sent verbatim as the `x-key` header. Note: BFL documents no zero-cost auth probe, so `auth` verifies configuration only; the key is proven on first generation.

## Operating Rules
1. Every `generate` spends prepaid credit: FLUX.2 klein from ~$0.014/image, pro from ~$0.03/MP, flex from ~$0.06/MP, max from ~$0.07/MP. Confirm with Michael before each generation.
2. FLUX has NO negative prompts. It ignores them. Reframe as a positive description before submitting.
3. RESULT URL EXPIRES IN 10 MINUTES. When status is Ready, download the sample immediately. Never store the URL as the artifact.
4. Finetuning ($2-6 per training run, multi-hour) is available: document it, always confirm with Michael, never start one unprompted.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/black-forest-labs.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/black-forest-labs.py

## Maturity
🧪 Draft: written from BFL's public API docs via the research dossier; not yet live-tested end-to-end.
