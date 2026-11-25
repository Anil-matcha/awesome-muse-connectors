---
name: "github"
description: "Work with GitHub: view profile, list repos, list and create issues. Trigger phrases: github, repo, issue, pull request."
metadata: { "includeInPrompt": true }
tagline: "View your profile, list repos, list open issues, and create issues."
catalog_auth: "personal access token (classic, scopes `repo` + `read:user`, per-user)"
catalog_hosts: ["api.github.com"]
---

# GitHub

## Purpose
Work with the user's GitHub account: verify identity, list repositories, list open issues, and create issues. Use when the user mentions GitHub, a repo, or wants an issue filed.

## Tooling
All commands go through `bin/github.py`:

```bash
bin/github.py auth                                              # verify the connection (GET /user)
bin/github.py repos                                             # list your repos (name, private, updated_at)
bin/github.py issues --repo OWNER/REPO                          # open issues in a repo
bin/github.py create-issue --repo OWNER/REPO --title "T" \
    --body "details"                                            # create an issue
```

## Auth
- Provider id: `github` (credential is collected as `custom.github`)
- Collection: personal access token (classic PAT) via the secure credential flow (`credentials.request_api_access`); create one at github.com → Settings → Developer settings → Personal access tokens → Tokens (classic) with scopes `repo` and `read:user`
- Required scopes: `repo`, `read:user`
- Allowed hosts: `api.github.com`
- Status check: `bin/github.py auth` (must print your login)

## Operating Rules
1. `create-issue` is a write: confirm the repo, title, and body with the user before creating, unless standing permission to file issues exists.
2. Reading (auth, repos, issues) needs no confirmation.
3. Respect GitHub rate limits (5,000 requests/hour for PATs); if a call returns 403 with `X-RateLimit-Remaining: 0`, wait until `X-RateLimit-Reset` and continue.
4. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/github.py`). Do not print, log, or transmit the token value.

## Files
- SKILL.md
- bin/github.py

## Maturity
🧪 Draft: written from GitHub's public REST API docs; not yet live-tested end-to-end.
