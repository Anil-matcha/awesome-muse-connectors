---
name: "hubspot"
description: "Read and manage the HubSpot CRM: contacts, contact search, deals. Trigger phrases: hubspot, CRM, contacts, deals, pipeline."
metadata: { "includeInPrompt": true }
tagline: "List and search contacts, create contacts, and list deals in your HubSpot CRM."
catalog_auth: "HubSpot private app token (per-user, HubSpot Settings \u2192 Integrations \u2192 Private Apps)"
catalog_hosts: ["api.hubapi.com"]
---

# HubSpot

## Purpose
Work with the user's HubSpot CRM: list contacts, search contacts, create contacts, and list deals. Use when the user mentions HubSpot, CRM, contacts, or their sales pipeline.

## Tooling
All commands go through `bin/hubspot.py`:

```bash
bin/hubspot.py contacts --limit 20                                  # list contacts
bin/hubspot.py search-contacts --query "acme"                       # search contacts
bin/hubspot.py create-contact --email jane@acme.com --firstname Jane --lastname Doe
bin/hubspot.py deals --limit 20                                     # list deals
```

## Auth
- Provider id: `hubspot` (credential is collected as `custom.hubspot`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`): a HubSpot private app token (HubSpot Settings → Integrations → Private Apps), pasted once into the hosted form
- Enable these scopes on the private app: `crm.objects.contacts.read`, `crm.objects.contacts.write`, `crm.objects.companies.read`, `crm.objects.deals.read`, `crm.objects.deals.write`
- Allowed hosts: `api.hubapi.com`
- Status check: `bin/hubspot.py contacts --limit 1` (must return a contacts list)

## Operating Rules
1. `create-contact` is a write: confirm the contact details with the user before creating, unless standing permission exists.
2. Reading (contacts, search-contacts, deals) needs no confirmation.
3. This skill is read-mostly by design; it ships no deal/contact deletion or update commands. Ask before adding any.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/hubspot.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/hubspot.py

## Maturity
🧪 Draft: written from HubSpot's public CRM API docs; not yet live-tested end-to-end.
