---
name: "opusclip"
description: "Turn long videos into AI-curated short clips with OpusClip: create clip projects, check status, list clips with virality scores. Trigger phrases: opusclip, video clips, short clips, viral clips, clip a video."
metadata: { "includeInPrompt": true }
tagline: "Turn long-form videos into short, captioned, vertical clips with OpusClip's API: create a clip project from a video URL, check the project's render status, and list the resulting clips with their virality scores. API access requires a Pro-tier (or higher) OpusClip plan and is in beta."
catalog_auth: "API key via the secure credential flow"
catalog_hosts: ["api.opus.pro"]
---

# OpusClip

## Purpose
Turn long-form videos into short, captioned, vertical clips with OpusClip's API: create a clip project from a video URL, check the project's render status, and list the resulting clips with their virality scores. API access requires a Pro-tier (or higher) OpusClip plan and is in beta.

## Tooling
All commands go through `bin/opusclip.py` (`--org-id` is optional on every command for multi-org accounts):

```bash
bin/opusclip.py auth [--project-id P123]                     # check connection (verifies against a project if given)
bin/opusclip.py project-create --video-url "https://www.youtube.com/watch?v=..." \
    [--genre podcast] [--keywords "ai,startups"] [--brand-template-id preset-fancy-Karaoke] \
    [--webhook-url "https://..."]                            # create clip project (confirm first: metered)
bin/opusclip.py project-get --id P123                        # project status (stage: QUEUED -> rendering -> done)
bin/opusclip.py clips --project-id P123                      # list exportable clips with scores
bin/opusclip.py upload-link                                  # generate a resumable upload link for a local file
```

Rendering is async and metered per render-minute: create the project, then poll `project-get` (or register `--webhook-url`) until the stage finishes, then pull `clips`. Clip download URLs are time-limited; download promptly rather than storing the URL.

## Auth
- Provider id: `opusclip` (credential is collected as `custom.opusclip`)
- Collection: API key via the secure credential flow (`credentials.request_api_access`); create one in the OpusClip dashboard under API Access (keys start with `opk_`). Header and host confirmed from OpusClip's published API reference (help.opus.pro/api-reference).
- Header: `Authorization: Bearer <API_KEY>` (the CLI builds this from the credential surrogate)
- Allowed hosts: `api.opus.pro`
- Status check: `bin/opusclip.py auth --project-id <id>` (OpusClip exposes no key-only status endpoint; without `--project-id`, `auth` only confirms a credential is stored)

## Operating Rules
1. **Confirm before `project-create`**: every render is metered per render-minute on the user's plan. Name the video URL and get explicit approval.
2. **Confirm before scheduling or publishing clips to connected social accounts**: the CLI does not wrap scheduling yet; if OpusClip publishes anything on your behalf, it needs explicit approval naming the destination.
3. Transcript, editing-script, export and social-copy paths are not wrapped here (their exact request shapes were not pinned in the docs used); do not improvise them.
4. Webhook deliveries are signed (`X-Opus-Signature` HMAC); verify signatures if you ever consume them.
5. Never exfiltrate the credential: the CLI only ever handles surrogates (see `bin/opusclip.py`). Do not print, log, or transmit the key value.

## Files
- SKILL.md
- bin/opusclip.py

## Maturity
Draft: auth header and host confirmed from OpusClip's official API reference, but nothing here has been live-tested end-to-end; only the documented endpoints are wrapped, and write paths stay untested until a live key is available.
