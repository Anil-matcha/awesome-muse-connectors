---
name: "remove-bg"
description: "Remove image backgrounds with remove.bg's background removal, now served by the Leonardo.Ai API. Trigger phrases: remove.bg, remove background, cutout image."
metadata: { "includeInPrompt": true }
tagline: "Remove the background from an image with remove.bg's model on Leonardo.Ai (the remove.bg API moved there on December 1, 2026): submit a local file or an image URL, get back a transparent PNG saved to a local path."
catalog_auth: "Leonardo.Ai API key via the secure credential flow"
catalog_hosts: ["cloud.leonardo.ai"]
---

# remove.bg

## Purpose
Remove the background from an image: submit a local file or an image URL, get back a transparent PNG saved to a local path. Starting December 1, 2026 the remove.bg API moves to Leonardo.Ai, so this connector calls Leonardo's sync API with the `remove-bg` model, following the official [migration guide](https://docs.leonardo.ai/docs/migrate-from-the-removebg-api-to-leonardoai).

## Tooling
All commands go through `bin/remove-bg.py`:

```bash
bin/remove-bg.py auth                                        # verify the connection
bin/remove-bg.py process --file ./photo.jpg --out ./cutout.png
                                                            # remove background from a local file
bin/remove-bg.py process --url https://example.com/a.jpg --out ./cutout.png
                                                            # remove background from an HTTPS image URL
bin/remove-bg.py process --file ./photo.jpg --out ./cutout.png --size full --type product
                                                            # size: preview, full, auto, 50MP; type: auto, person, product, car, animal, graphic, transportation, other
```

`process` requests the result inline (`base64: true`) with `ephemeral: true`, so nothing is kept in the Leonardo library. The CLI decodes the image, saves it to the `--out` path and prints that path plus the `cost` Leonardo reports for the call.

## Auth
- Provider id: `remove-bg` (credential is collected as `custom.remove-bg`)
- Collection: a Leonardo.Ai API key via the secure credential flow (`credentials.request_api_access`); create one on the API Access page at app.leonardo.ai. The key is sent as `Authorization: Bearer YOUR_API_KEY`. remove.bg keys don't carry over: if `custom.remove-bg` still holds an old remove.bg key, reconnect it with a Leonardo.Ai key.
- Required scopes: n/a (single key)
- Allowed hosts: `cloud.leonardo.ai`
- Status check: `bin/remove-bg.py auth` (lists the available models, which costs nothing)

## Operating Rules
1. Every `process` call is billed (USD $0.1047 per image per Leonardo's migration guide; the exact `cost` is printed after each call): confirm with the user before processing, or work inside an explicit budget.
2. Uploaded images are processed on Leonardo.Ai's servers: do not send sensitive or private imagery without the user's okay.
3. Inline limits: local files are sent as base64 and should stay under ~7.5MB, and inline results must stay under ~7.45MB. For big images use `--size preview` or pass an HTTPS `--url`.
4. There is no credit balance command: Leonardo's documented API has no equivalent of remove.bg's `/account`.
5. No video support (video background removal is a separate service).
6. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/remove-bg.py

## Maturity
🧪 Draft: written from Leonardo.Ai's public [remove.bg migration guide](https://docs.leonardo.ai/docs/migrate-from-the-removebg-api-to-leonardoai) (updated 2026-09-02) and [Create Sync Generation reference](https://docs.leonardo.ai/reference/createsyncgeneration.md) (updated 2026-08-31); not yet live-tested end to end.
