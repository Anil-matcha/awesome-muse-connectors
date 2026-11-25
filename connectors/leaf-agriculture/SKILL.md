---
name: "leaf-agriculture"
description: "Read and manage farm data through Leaf Agriculture: fields, boundaries, machine operation files, and as-applied irrigation. Trigger phrases: leaf agriculture, farm data, field boundaries, as-applied irrigation, john deere data, operation files."
metadata: { "includeInPrompt": true }
tagline: "Read and manage farm data through Leaf Agriculture, a unified farm-data API that aggregates the partner-gated OEM platforms under self-serve access: John Deere, CNH Industrial (Case IH/New Holland), Climate FieldView, Trimble, Raven and AgLeader. The primitives it exposes (fields, boundaries, machine operation files for planting/harvest/application/tillage, plus as-applied irrigation) are exactly what a farmer-first fintech and supply-chain digitization product consumes. This is the practical route to partner-gated OEM data without a partnership agreement: individual provider connections need that grower's OAuth consent, which is the normal data-access model rather than a partnership gate."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.withleaf.io"]
---

# Leaf Agriculture

## Purpose
Read and manage farm data through Leaf Agriculture, a unified farm-data API that aggregates the partner-gated OEM platforms under self-serve access: John Deere, CNH Industrial (Case IH/New Holland), Climate FieldView, Trimble, Raven and AgLeader. The primitives it exposes (fields, boundaries, machine operation files for planting/harvest/application/tillage, plus as-applied irrigation) are exactly what a farmer-first fintech and supply-chain digitization product consumes. This is the practical route to partner-gated OEM data without a partnership agreement: individual provider connections need that grower's OAuth consent, which is the normal data-access model rather than a partnership gate.

## Tooling
All commands go through `bin/leaf-agriculture.py`. Every command takes `--user-id` (the Leaf user id from the Leaf dashboard):

```bash
bin/leaf-agriculture.py auth --user-id USER_ID          # verify the API key
bin/leaf-agriculture.py fields --user-id USER_ID        # list fields
bin/leaf-agriculture.py field-get --user-id USER_ID \
    --field-id FIELD_ID                                 # one field
bin/leaf-agriculture.py field-create --user-id USER_ID \
    --file field.json                                   # create a field record
bin/leaf-agriculture.py field-update --user-id USER_ID \
    --field-id FIELD_ID --file field.json               # update a field record
bin/leaf-agriculture.py field-delete --user-id USER_ID \
    --field-id FIELD_ID \
    --confirm "delete field FIELD_ID"                    # delete a field record (confirmation required)
bin/leaf-agriculture.py field-sync --user-id USER_ID    # trigger a manual field sync from providers
bin/leaf-agriculture.py field-push --user-id USER_ID \
    --field-id FIELD_ID --provider john-deere \
    --confirm "push field FIELD_ID to john-deere"        # push field data into a provider (confirmation required)
bin/leaf-agriculture.py operation-files --user-id USER_ID \
    --field-id FIELD_ID                                 # machine operation files for a field
bin/leaf-agriculture.py irrigation --user-id USER_ID    # as-applied irrigation events
```

`--provider` names the target provider for a push, e.g. `john-deere`, `cnhi`, `climate-fieldview`, `trimble`, `raven`, `agleader`.

## Auth
- Provider id: `leaf-agriculture` (credential is collected as `custom.leaf-agriculture`)
- Collection: Bearer API key via the secure credential flow (`credentials.request_api_access`); issued in the Leaf dashboard
- Auth scheme: `Authorization: Bearer <token>` on every request; placement is resolved by the helper from the credential config
- Allowed hosts: `api.withleaf.io`
- Base path pattern: `https://api.withleaf.io/services/{service}/api` (e.g. `/services/fields/api`, `/services/irrigation/api`)
- The Leaf user id is not a secret; pass it as `--user-id` on every command
- Status check: `bin/leaf-agriculture.py auth --user-id USER_ID`
- Honesty note: pricing and exact sandbox semantics were open items in the research dossier and could not be confirmed without live access; test against preview fields before enabling provider sync, and check docs.withleaf.io for current pricing.

## Operating Rules
1. **No direct physical actuation.** This connector moves farm data only: records, boundaries, operation files, irrigation logs. Nothing here starts a tractor or opens a valve.
2. Field create/update/delete sync to connected providers, so bad writes corrupt the farm's data picture downstream. Confirm the field id and payload with the user before create/update, and `field-delete` requires the exact `--confirm` string the CLI echoes.
3. `field-push` is MEDIUM: it pushes boundaries or prescriptions into a provider such as John Deere Operations Center, where equipment or operators may act on them. It requires the exact `--confirm` string every time.
4. Rate limits apply per API key. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/leaf-agriculture.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/leaf-agriculture.py

## Maturity
Draft: written from Leaf Agriculture's public API docs; not yet live-tested end-to-end.
