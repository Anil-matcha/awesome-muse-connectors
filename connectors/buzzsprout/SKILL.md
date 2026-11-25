---
name: "buzzsprout"
description: "Manage Buzzsprout podcast hosting: episodes and players via its JSON API. Trigger phrases: buzzsprout, podcast episodes, publish episode, podcast hosting."
metadata: { "includeInPrompt": true }
tagline: "Manage podcast episodes on Buzzsprout: list and fetch episodes, create, update, or delete them, and list embed players. Use when the user wants to publish or manage podcast episodes on a Buzzsprout-hosted show."
catalog_auth: "API token via the secure credential flow"
catalog_hosts: ["www.buzzsprout.com"]
---

# Buzzsprout

## Purpose
Manage podcast episodes on Buzzsprout: list and fetch episodes, create, update, or delete them, and list embed players. Use when the user wants to publish or manage podcast episodes on a Buzzsprout-hosted show.

## Tooling
All commands go through `bin/buzzsprout.py`. Every command takes `--podcast-id` because the podcast id is part of the API path:

```bash
bin/buzzsprout.py auth --podcast-id 12345                                  # verify the API token
bin/buzzsprout.py episodes --podcast-id 12345                              # list episodes
bin/buzzsprout.py episode-get --podcast-id 12345 --episode-id 6789         # get one episode
bin/buzzsprout.py episode-create --podcast-id 12345 \
    --payload '{"title":"Ep 12","description":"...","audio_url":"https://..."}'  # create (confirm first)
bin/buzzsprout.py episode-update --podcast-id 12345 --episode-id 6789 \
    --payload '{"title":"New title"}'                                      # update (confirm first)
bin/buzzsprout.py episode-delete --podcast-id 12345 --episode-id 6789      # delete (confirm first)
bin/buzzsprout.py players --podcast-id 12345                              # list embed players
```

API quirks handled by the CLI (you do not need to think about them): every URL ends in `.json`, POST/PUT send `Content-Type: application/json; charset=utf-8` (Buzzsprout returns 415 without it), auth is the literal header `Authorization: Token token=<token>` (no whitespace after `token=`), and a custom User-Agent is sent on every request (Buzzsprout requires one).

## Auth
- Provider id: `buzzsprout` (credential is collected as `custom.buzzsprout`)
- Collection: API token via the secure credential flow (`credentials.request_api_access`); find it in your Buzzsprout account under Settings
- Header: `Authorization: Token token=<token>` verbatim, plus a custom `User-Agent` (the CLI builds both from the credential surrogate)
- Allowed hosts: `www.buzzsprout.com`
- Status check: `bin/buzzsprout.py auth --podcast-id <id>` (lists episodes; a successful list proves the token works)

## Operating Rules
1. **Confirm before creating, updating, or deleting an episode**: name the show, episode title, and what will change. No exceptions.
2. `--podcast-id` is required on every command; double-check it matches the intended show before any write.
3. Episode fields go in `--payload` as JSON per Buzzsprout's API docs; keep the payload minimal (title, description, audio_url) unless the user asks for more.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/buzzsprout.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/buzzsprout.py

## Maturity
Draft: written from Buzzsprout's public API docs; not yet live-tested end-to-end.
