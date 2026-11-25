---
name: "webflow"
description: "Manage Webflow sites: list sites and CMS collections, read and edit CMS items, and publish. Trigger phrases: webflow, webflow cms, publish webflow site."
metadata: { "includeInPrompt": true }
tagline: "Work with the Webflow Data API v2: list sites, inspect site details, browse CMS collections and items, create/update/delete CMS items, and publish a site. Uses a per-site token from Site Settings."
catalog_auth: "per-site token via the secure credential flow"
catalog_hosts: ["api.webflow.com"]
---

# Webflow

## Purpose
Work with the Webflow Data API v2: list sites, inspect site details, browse CMS collections and items, create/update/delete CMS items, and publish a site. Uses a per-site token from Site Settings.

## Tooling
All commands go through `bin/webflow.py`:

```bash
bin/webflow.py auth                                        # verify the connection (lists accessible sites)
bin/webflow.py sites                                       # list sites
bin/webflow.py site --id SITE_ID                           # site details (domains, publish status)
bin/webflow.py collections --site-id SITE_ID               # list CMS collections on a site
bin/webflow.py items --collection-id COLLECTION_ID         # list CMS items in a collection
bin/webflow.py create-item --collection-id COLLECTION_ID --data '{"items":[{"fieldData":{"name":"Hello"}}]}'
                                                           # create CMS item(s) (raw JSON body, per Webflow docs)
bin/webflow.py update-item --collection-id COLLECTION_ID --item-id ITEM_ID --data '{"fieldData":{"name":"New name"}}'
                                                           # update a CMS item (raw JSON body, per Webflow docs)
bin/webflow.py delete-item --collection-id COLLECTION_ID --item-id ITEM_ID   # delete a CMS item
bin/webflow.py publish --site-id SITE_ID                   # publish the site
```

## Auth
- Provider id: `webflow` (credential is collected as `custom.webflow`)
- Collection: per-site token via the secure credential flow (`credentials.request_api_access`); generate one in Webflow at Site Settings, Integrations, API access (workspace tokens are enterprise-only, so site tokens are the default)
- Required scopes: whatever scopes were granted to the site token
- Allowed hosts: `api.webflow.com`
- Status check: `bin/webflow.py auth`

## Operating Rules
1. Confirm with the user before publishing a site or CMS items and before deleting items: these change the live site.
2. Rate limit is about 60 requests/minute: keep calls modest and honor `Retry-After` / `X-RateLimit-Remaining` headers.
3. The API is server-side only (browser clients are CORS-blocked); always call it from this CLI, never from a page.
4. Never exfiltrate the credential: the CLI only ever handles surrogates. Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/webflow.py

## Maturity
🧪 Draft: written from Webflow's public Data API v2 docs; not yet live-tested end to end.
