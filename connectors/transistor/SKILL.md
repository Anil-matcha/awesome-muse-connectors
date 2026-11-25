---
name: "transistor"
description: "Manage Transistor.fm podcast hosting, from episode drafts to audio uploads. Trigger phrases: transistor, transistor.fm, podcast hosting, publish episode."
metadata: { "includeInPrompt": true }
tagline: "Manage podcast hosting on Transistor.fm: list shows and episodes, create draft episodes, update or delete them, and upload episode audio via Transistor's two-step upload flow. Use when the user wants to publish or manage podcast episodes programmatically."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.transistor.fm"]
---

# Transistor

## Purpose
Manage podcast hosting on Transistor.fm: list shows and episodes, create draft episodes, update or delete them, and upload episode audio via Transistor's two-step upload flow. Use when the user wants to publish or manage podcast episodes programmatically.

## Tooling
All commands go through `bin/transistor.py`:

```bash
bin/transistor.py auth                                          # verify the API key
bin/transistor.py shows                                         # list your shows
bin/transistor.py episodes --show-id SHOW_ID                    # list episodes of a show
bin/transistor.py episode-create --show-id SHOW_ID --title "Ep 12" \
    --audio-url "https://.../ep12.mp3" [--description "..."]     # create a DRAFT episode
bin/transistor.py episode-update --id EP_ID --title "New title" # update title/description
bin/transistor.py episode-delete --id EP_ID                     # delete an episode
bin/transistor.py authorize-upload                              # step 1 of audio upload (prints raw JSON)
bin/transistor.py upload --file ./ep12.mp3 --show-id SHOW_ID \
    --title "Ep 12"                                             # authorize -> PUT -> create draft
```

Audio upload is two steps: `authorize-upload` returns the provider's upload target (raw JSON, so you can see the exact fields), then the file is PUT there. `upload` runs the whole flow (authorize, PUT, create draft episode) in one command; if the authorize response does not expose a recognizable audio URL, it stops after the PUT and tells you to finish with `episode-create --audio-url`.

## Auth
- Provider id: `transistor` (credential is collected as `custom.transistor`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); create one in your Transistor account settings
- Header: `x-api-key: <key>` verbatim, raw key, no Bearer prefix (the CLI builds this header from the credential surrogate)
- Allowed hosts: `api.transistor.fm`
- Status check: `bin/transistor.py auth` (lists your shows; a successful list proves the key works)

## Operating Rules
1. **Confirm before creating, updating, deleting, or uploading**: name the show, episode title, and what will change. Creating a draft is low-risk but still confirm; publishing, deleting, or uploading always needs explicit approval.
2. `episode-create` makes a draft by default; do not publish without a separate explicit confirmation.
3. `upload` consumes storage on the user's Transistor plan; confirm the file and show first.
4. The key is account-scoped: you can only touch the user's own shows.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/transistor.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/transistor.py

## Maturity
Draft: written from Transistor's public API docs; not yet live-tested end-to-end. The `authorize_upload` response field names are not pinned in the docs used, so `upload` extracts the upload/audio URLs on a best-effort basis and stops with the raw JSON instead of guessing.
