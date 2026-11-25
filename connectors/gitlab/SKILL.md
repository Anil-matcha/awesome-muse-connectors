---
name: "gitlab"
description: "Read and write GitLab: your user, projects, open merge requests, create issues. Trigger phrases: gitlab, merge request, gitlab issue."
metadata: { "includeInPrompt": true }
tagline: "Your GitLab user, projects, open merge requests, and issue creation."
catalog_auth: "personal access token (per-user, gitlab.com \u2192 Preferences \u2192 Access Tokens; `read_api` for reads, `api` to create issues)"
catalog_hosts: ["gitlab.com"]
---

# GitLab

## Purpose
Read and write the user's GitLab: who the token belongs to, project list, open merge requests for a project, and issue creation. Use when the user mentions GitLab, merge requests, or wants something filed as a GitLab issue.

## Tooling
All commands go through `bin/gitlab.py`:

```bash
bin/gitlab.py me                                              # verify the connection
bin/gitlab.py projects                                        # your projects
bin/gitlab.py mrs --project 123456                            # open merge requests
bin/gitlab.py create-issue --project 123456 --title "Bug: ..."  # create an issue
```

`--project` accepts a numeric project ID or a `group/project` path (URL-encoded automatically).

## Auth
- Provider id: `gitlab` (credential is collected as `custom.gitlab`)
- Collection: personal access token from gitlab.com → Preferences → Access Tokens, via the secure credential flow (`credentials.request_api_access`). The `read_api` scope is enough for reads; creating issues needs the `api` scope.
- Connect placement: bearer_header
- Allowed hosts: `gitlab.com`
- Status check: `bin/gitlab.py me` (must return your user)

## Operating Rules
1. `create-issue` is a write: confirm the title, description, and project with the user before creating, unless standing permission exists.
2. Reading (me, projects, mrs) needs no confirmation.
3. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/gitlab.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/gitlab.py

## Maturity
🧪 Draft: written from GitLab's public API docs; not yet live-tested end-to-end.
