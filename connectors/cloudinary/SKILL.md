---
name: "cloudinary"
description: "Manage Cloudinary media: upload images and videos, list and inspect assets, update metadata, delete assets, and check plan usage. Trigger phrases: cloudinary, upload image, cloudinary usage."
metadata: { "includeInPrompt": true }
tagline: "Manage media on Cloudinary through the Upload and Admin APIs: upload images and videos, list and inspect assets, update metadata and tags, delete assets, and check plan usage (credits, storage, bandwidth, transformations)."
catalog_auth: "cloud_name + API key + secret via the secure credential flow"
catalog_hosts: ["api.cloudinary.com"]
---

# Cloudinary

## Purpose
Manage media on Cloudinary through the Upload and Admin APIs: upload images and videos, list and inspect assets, update metadata and tags, delete assets, and check plan usage (credits, storage, bandwidth, transformations).

## Tooling
All commands go through `bin/cloudinary.py`:

```bash
bin/cloudinary.py auth                                        # verify the connection (also shows plan usage)
bin/cloudinary.py usage                                       # plan usage: credits, storage, bandwidth, transformations
bin/cloudinary.py upload --file ./photo.jpg                  # upload an image
bin/cloudinary.py upload --file ./clip.mp4 --resource-type video   # upload a video
bin/cloudinary.py upload --file ./photo.jpg --folder products # upload into a folder
bin/cloudinary.py list --prefix products/ --max-results 20    # list image assets
bin/cloudinary.py get --public-id products/photo1            # asset details
bin/cloudinary.py update --public-id products/photo1 --data '{"tags":["summer"],"context":{"caption":"Beach"}}'
                                                             # update metadata/tags (raw JSON body, per Cloudinary docs)
bin/cloudinary.py delete --public-id products/photo1         # delete an asset
```

## Auth
- Provider id: `cloudinary` (credential is collected as `custom.cloudinary`)
- Collection: via the secure credential flow (`credentials.request_api_access`) as a single colon-joined value `cloud_name:api_key:api_secret`; the three parts come from the Cloudinary Console at Settings, API Keys. The collection step stores them as three named entries (`cloud_name`, `api_key`, `api_secret`) under `custom.cloudinary`; the CLI splits them at use: `cloud_name` goes into the request host, and `api_key:api_secret` go into the HTTP Basic auth header.
- Required scopes: n/a (account API key pair)
- Allowed hosts: `api.cloudinary.com`
- Status check: `bin/cloudinary.py auth`
- Wire format (verbatim from Cloudinary's docs): `Authorization: Basic base64(api_key:api_secret)` against `https://api.cloudinary.com/v1_1/{cloud_name}`.

## Operating Rules
1. The free plan is credit-based across storage/bandwidth/transformations: run `usage` before heavy work and stay inside the plan.
2. Confirm with the user before uploading (it consumes bandwidth/transformation quota) and before deleting (deletes are permanent).
3. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key, secret, or cloud name values.

## Files
- SKILL.md
- bin/cloudinary.py

## Maturity
🧪 Draft: written from Cloudinary's public Upload and Admin API docs; not yet live-tested end to end. The three-part credential split (single collected value, split into entries at use) is the design assumption to re-verify on first live run.
