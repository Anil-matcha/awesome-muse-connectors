---
name: "unsplash"
description: "Search Unsplash for free stock photos, browse by photographer or topic, and download images with proper attribution credit. Trigger phrases: unsplash, stock photo, find an image, download unsplash image."
metadata: { "includeInPrompt": true }
tagline: "Search Unsplash's free stock photo library, browse the latest photos, look up a photo's details, browse a photographer's portfolio or a topic, and download an image while honoring Unsplash's API guidelines. At the Client-ID tier this connector is read-only."
catalog_auth: "access key via the secure credential flow"
catalog_hosts: ["api.unsplash.com"]
---

# Unsplash

## Purpose
Search Unsplash's free stock photo library, browse the latest photos, look up a photo's details, browse a photographer's portfolio or a topic, and download an image while honoring Unsplash's API guidelines. At the Client-ID tier this connector is read-only.

## Tooling
All commands go through `bin/unsplash.py`:

```bash
bin/unsplash.py auth                                        # verify the connection
bin/unsplash.py search --query "desert road"                # search photos
bin/unsplash.py search --query "coffee" --orientation portrait --per-page 5
bin/unsplash.py list --per-page 5                           # latest photos
bin/unsplash.py photo --id PHOTO_ID                         # one photo's details and URLs
bin/unsplash.py user-photos --username USERNAME             # a photographer's photos
bin/unsplash.py topic --id TOPIC_ID                         # photos in a topic
bin/unsplash.py download --id PHOTO_ID --out ./photo.jpg    # download an image file
```

`download` hits the photo's `download_location` URL first (required by Unsplash's guidelines: it credits the photographer and keeps the API access in good standing), then saves the image bytes to `--out`. Do not hotlink the CDN URL in production: download and self-host.

## Auth
- Provider id: `unsplash` (credential is collected as `custom.unsplash`)
- Collection: access key via the secure credential flow (`credentials.request_api_access`); create a free developer app at unsplash.com/developers. The key is sent as `Authorization: Client-ID YOUR_ACCESS_KEY`.
- Required scopes: n/a at Client-ID tier (public read actions)
- Allowed hosts: `api.unsplash.com`
- Status check: `bin/unsplash.py auth`

## Operating Rules
1. Read-only at the Client-ID tier: there are no writes to confirm.
2. Rate limits: about 50 requests/hour for demo apps, 5,000/hour for approved production apps; a 429 means slow down.
3. Always use `download` (never raw CDN hotlinking) when an image is used, so the `download_location` guideline is honored, and include the photographer credit ("Photo by [Name] on Unsplash") wherever the image is shown.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/unsplash.py

## Maturity
🧪 Draft: written from Unsplash's public API docs; not yet live-tested end to end.
