---
name: "canva"
description: "Work with Canva designs: list designs and folders, create designs, upload assets, and export to PNG/JPG/PDF/MP4. Trigger phrases: canva, canva design, export canva design."
metadata: { "includeInPrompt": true }
tagline: "Read and manage Canva designs through the Canva Connect API: list designs and folders, inspect a design, create designs, upload assets, and export designs. Exports are async jobs: submit with export, then poll with export-status until the job succeeds."
catalog_auth: "provider OAuth 2.0 + PKCE via the secure credential flow"
catalog_hosts: ["api.canva.com"]
---

# Canva

## Purpose
Read and manage Canva designs through the Canva Connect API: list designs and folders, inspect a design, create designs, upload assets, and export designs. Exports are async jobs: submit with `export`, then poll with `export-status` until the job succeeds.

## Tooling
All commands go through `bin/canva.py`:

```bash
bin/canva.py auth                                        # verify the connection (prints the Canva user)
bin/canva.py designs --query "pitch deck"                # list designs, optional search
bin/canva.py design --id DESIGN_ID                      # get one design's details
bin/canva.py folders                                     # list folders
bin/canva.py folder-items --id FOLDER_ID                 # list items in a folder
bin/canva.py assets                                      # list uploaded assets
bin/canva.py create --data '{"design_type":{"type":"preset","name":"presentation"}}'
                                                         # create a design (raw JSON body, per Canva docs)
bin/canva.py upload-asset --file ./logo.png              # upload a local file as an asset
bin/canva.py upload-asset --url https://example.com/a.png  # import an asset from a URL
bin/canva.py export --design-id DESIGN_ID --format png   # submit an async export job (png, jpg, pdf, mp4, ...)
bin/canva.py export-status --id EXPORT_ID                # poll the export job; prints download URLs when done
```

## Auth
- Provider id: `canva` (credential is collected as `custom.canva`)
- Collection: OAuth 2.0 authorization-code + PKCE via the secure credential flow (`credentials.request_api_access`); any Canva account can create a developer integration for free, but using it for other users requires Canva app review
- Required scopes: whatever the Canva integration granted (design read/write as configured)
- Allowed hosts: `api.canva.com`
- Status check: `bin/canva.py auth`

## Operating Rules
1. Access tokens expire after about 4 hours; the credential flow handles refresh, but re-run `auth` if calls start failing.
2. Exports are async: `export` returns a job id, then poll `export-status` with backoff until the status is `success`. Download URLs expire, so download the file promptly and never store the URL as the artifact.
3. Confirm with the user before creating designs, uploading assets, running exports, or deleting anything: each burns Canva usage or changes the account.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/canva.py

## Maturity
🧪 Draft: written from Canva's public Connect API docs; not yet live-tested end to end.
