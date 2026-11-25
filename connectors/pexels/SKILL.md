---
name: "pexels"
description: "Search Pexels for royalty-free stock photos and videos, browse curated and popular media, and inspect collections. Trigger phrases: pexels, stock photo, stock video, find an image."
metadata: { "includeInPrompt": true }
tagline: "Search Pexels' royalty-free stock library: find photos and videos by keyword, browse curated/trending photos and popular videos, look up a single photo or video, and read collection contents. The Pexels API is read-only, so this connector cannot change anything."
catalog_auth: "free API key via the secure credential flow"
catalog_hosts: ["api.pexels.com"]
---

# Pexels

## Purpose
Search Pexels' royalty-free stock library: find photos and videos by keyword, browse curated/trending photos and popular videos, look up a single photo or video, and read collection contents. The Pexels API is read-only, so this connector cannot change anything.

## Tooling
All commands go through `bin/pexels.py`:

```bash
bin/pexels.py auth                                        # verify the connection
bin/pexels.py search --query "misty forest"               # search photos
bin/pexels.py search --query "ocean" --orientation landscape --per-page 5
bin/pexels.py curated --per-page 5                        # trending photos, updated hourly
bin/pexels.py photo --id 1234567                          # one photo's details and file URLs
bin/pexels.py search-videos --query "city night"          # search videos
bin/pexels.py popular-videos --per-page 5                # popular videos
bin/pexels.py video --id 1234567                          # one video's details and file URLs
bin/pexels.py collection --id abc123                      # contents of a collection
```

Photo and video results include source file URLs at several sizes: pick the size that fits the use.

## Auth
- Provider id: `pexels` (credential is collected as `custom.pexels`)
- Collection: free API key via the secure credential flow (`credentials.request_api_access`); get one at pexels.com/api. The key is sent verbatim as `Authorization: YOUR_API_KEY` with no Bearer prefix.
- Required scopes: n/a (single key)
- Allowed hosts: `api.pexels.com`
- Status check: `bin/pexels.py auth`

## Operating Rules
1. Read-only API: there are no writes to confirm.
2. Monthly request quota: watch the `X-Ratelimit-Limit`, `X-Ratelimit-Remaining`, and `X-Ratelimit-Reset` response headers on 2xx responses and stay inside the plan's quota.
3. Pexels media is royalty-free, but keep photographer credit where it is shown.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/pexels.py

## Maturity
🧪 Draft: written from Pexels' public API docs; not yet live-tested end to end.
