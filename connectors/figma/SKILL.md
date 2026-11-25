---
name: "figma"
description: "Look up your Figma user, read file metadata, and post comments on files. Trigger phrases: figma, figma file, design file."
metadata: { "includeInPrompt": true }
tagline: "Look up your Figma user, read file metadata, and post comments on files."
catalog_auth: "Figma personal access token (per-user, Figma Settings \u2192 Personal access tokens)"
catalog_hosts: ["api.figma.com"]
---

# Figma

## Purpose
Read from the user's Figma: the authenticated user (`me`) and file metadata (`file`: name, lastModified, version, thumbnailUrl). The full file document is intentionally not returned: it is too large to be useful in chat, so `file` surfaces metadata only. The `comment` command posts a comment to a file (plain text, or anchored to a node with `--node-id`); positioned canvas pins (x/y without a node) are not supported because the exact `client_meta` schema is not clearly defined in Figma's public docs.

## Tooling
All commands go through `bin/figma.py`:

```bash
bin/figma.py me                 # authenticated user (handle, email)
bin/figma.py file --key KEY     # file metadata: name, lastModified, version, thumbnailUrl

# Comment posts need an exact --confirm string (the CLI prints the required string on refusal)
bin/figma.py comment --key KEY --message "Looks great!" \
  --confirm 'post comment on file KEY: "Looks great!"'
bin/figma.py comment --key KEY --node-id 1:42 --message "Spacing looks off here." \
  --confirm 'post comment on file KEY: "Spacing looks off here."'
```

Get the file key from a Figma URL: it is the segment after `/file/` or `/design/`.

## Auth
- Provider id: `figma` (credential is collected as `custom.figma`)
- Collection: personal access token via the secure credential flow (`credentials.request_api_access`): create one in Figma → Settings → Personal access tokens (needs at least the `file_content:read` scope for `file`; `comment` additionally needs `file_comments:write`)
- Connect placement: `custom_header:X-Figma-Token` (Figma PATs use `X-Figma-Token`, not `Authorization: Bearer`)
- Allowed hosts: `api.figma.com`
- Status check: `bin/figma.py me` (a successful response proves the token works)

## Operating Rules
1. `comment` needs an exact `--confirm` string echoed by the CLI on every post; the CLI prints the required string when it refuses. Reading needs no confirmation.
2. Only node-anchored (`--node-id`) or plain comments ship: raw x/y canvas pins are not supported because Figma's `client_meta` schema is not clearly documented.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/figma.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/figma.py

## Maturity
🧪 Draft: written from Figma's public REST API docs (including the post-comment endpoint); not yet live-tested end-to-end.
