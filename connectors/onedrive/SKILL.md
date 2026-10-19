---
name: "onedrive"
description: "OneDrive files via Microsoft Graph: list, search, download, upload, mkdir, rename, move, recycle. Trigger phrases: onedrive, my files, upload to onedrive, download from onedrive."
metadata: { "includeInPrompt": true }
tagline: "OneDrive via Microsoft Graph: list, search, download, upload, mkdir, rename, move, recycle — with confirm-before-write and the Personal Vault always off-limits."
catalog_auth: "OAuth 2.0 (delegated) via the secure credential flow"
catalog_hosts: ["graph.microsoft.com"]
---

# OneDrive

## Purpose
Work with the user's OneDrive through the Microsoft Graph API: list folders, search files, download, upload, create folders, rename, move, and recycle items. Use when the user mentions OneDrive or asks to fetch, store, or organize files there.

Source: Microsoft Graph OneDrive / driveItem documentation (learn.microsoft.com/graph), checked 2026-10-19.

## Tooling
All commands go through `bin/onedrive.py`:

```bash
bin/onedrive.py me                                            # status check: verify auth, show the signed-in user
bin/onedrive.py ls [folder] [--limit N]                       # list a folder (default: root)
bin/onedrive.py search <query> [--limit N]                    # search OneDrive
bin/onedrive.py download <remote-path> <local-path>           # download a file

# Writes — every one requires --confirm naming the exact effect:
bin/onedrive.py upload <local-path> <remote-path> --confirm "upload report.pdf to Documents/report.pdf"
bin/onedrive.py mkdir <remote-path> --confirm "create folder Documents/Projects"
bin/onedrive.py rename <remote-path> <new-name> --confirm "rename Documents/a.txt to b.txt"
bin/onedrive.py move <remote-path> <dest-folder> --confirm "move Documents/a.txt to Archive"
bin/onedrive.py recycle <remote-path> --confirm "recycle Documents/old.txt"
```

Paths are OneDrive-relative (`Documents/file.pdf`), not local paths, except where a command names a local file. Large uploads use Graph's simple upload (PUT content); chunked upload sessions for very large files are out of scope for this CLI.

## Auth
- Provider id: `onedrive` (credential is collected as `custom.onedrive`)
- Collection: OAuth 2.0 delegated grant via the secure credential flow (`credentials.request_api_access`) — the user signs in with their Microsoft account and consents to Files access (the token endpoint is `login.microsoftonline.com`; all API calls go to Graph).
- Required scopes: `Files.ReadWrite` (delegated) for the signed-in user's drive.
- Allowed hosts: `graph.microsoft.com`
- Status check: `bin/onedrive.py me`

## Operating Rules
1. **Writes are confirmation-gated in code.** `upload`, `mkdir`, `rename`, `move`, and `recycle` refuse to run without `--confirm "<exact effect>"`. Get the user's confirmation in conversation first; never pre-fill it on their behalf. Reads (`me`, `ls`, `search`, `download`) need no confirmation.
2. **The Personal Vault is always off-limits** — the CLI refuses any path containing "personal vault", no exceptions, even for reads initiated by name.
3. `recycle` is recoverable (consumer OneDrive moves the item to the recycle bin); this CLI never empties the recycle bin and has no permanent-delete command.
4. Downloads follow Graph's 302 redirect to a pre-authenticated download URL. That URL is itself a bearer credential: the CLI never attaches our token to it, and never logs or persists the full URL.
5. A 401/403 is a question about the request before it is a question about the credential — confirm the surrogate was attached. Never print, log, or persist raw tokens; the CLI only ever handles surrogates.

## Files
- SKILL.md
- bin/onedrive.py

## Maturity
✅ Live — this is the production version from a running Muse setup: list/search/download/upload run against a live OneDrive as part of a file-placement workflow (inventory, downloads, and uploads verified against Microsoft Graph). Live-tested 2026-10-19. The `--confirm` write gate is enforced in the CLI in this catalog version.
