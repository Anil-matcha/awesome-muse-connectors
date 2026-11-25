---
name: "podbean"
description: "Manage Podbean podcast hosting: podcasts and episodes via OAuth API. Trigger phrases: podbean, podcast hosting, publish episode, podcast episodes."
metadata: { "includeInPrompt": true }
tagline: "Manage podcast hosting on Podbean: list podcasts and their episodes, create, update, or delete episodes. Podbean's analytics endpoints are a differentiator; the download/analytics report paths are not yet mapped in this connector."
catalog_auth: "provider OAuth 2.0 via the secure credential flow"
catalog_hosts: ["api.podbean.com"]
---

# Podbean

## Purpose
Manage podcast hosting on Podbean: list podcasts and their episodes, create, update, or delete episodes. Podbean's analytics endpoints are a differentiator; the download/analytics report paths are not yet mapped in this connector (see Maturity).

## Tooling
All commands go through `bin/podbean.py`:

```bash
bin/podbean.py auth                                            # verify the OAuth token
bin/podbean.py podcasts                                        # list podcasts on the account
bin/podbean.py episodes --podcast-id PODCAST_ID [--limit 20]   # list episodes
bin/podbean.py episode-create \
    --payload '{"title":"Ep 12","desc":"...","audio_url":"https://..."}'  # create (confirm first)
bin/podbean.py episode-update --episode-id EP_ID \
    --payload '{"title":"New title"}'                          # update (confirm first)
bin/podbean.py episode-delete --episode-id EP_ID                # delete (confirm first)
```

Episode fields go in `--payload` as JSON, following Podbean's API docs. Media upload uses Podbean's authorize-upload flow, which is not wrapped here yet: upload the file through Podbean's dashboard or API first, then pass the resulting URL in the create payload.

## Auth
- Provider id: `podbean` (credential is collected as `custom.podbean`)
- Collection: provider OAuth 2.0 (authorization-code) via the secure credential flow (`credentials.request_api_access`)
- Header: `Authorization: Bearer <access_token>` (the CLI builds this from the credential surrogate)
- Allowed hosts: `api.podbean.com`
- Status check: `bin/podbean.py auth` (lists podcasts; a successful list proves the token works)

## Operating Rules
1. **Confirm before creating, updating, or deleting an episode**: name the podcast, episode title, and what will change. No exceptions.
2. Episode payloads follow Podbean's published API schema; keep them minimal unless the user asks for more.
3. Analytics/download report endpoints are not implemented yet; do not improvise paths for them.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/podbean.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/podbean.py

## Maturity
Draft: written from Podbean's public API docs; not yet live-tested end-to-end. Analytics/download report endpoints and the media authorize-upload flow are documented by Podbean but not wrapped here yet.
