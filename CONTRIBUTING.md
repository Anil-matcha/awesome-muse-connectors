# Contributing to Awesome Muse Connectors

Thanks for helping expand and improve the connector catalog. Connector pull requests are the main contribution path; workflow templates are also welcome.

## Add a connector

Create one self-contained folder under `connectors/<provider-id>/`. Start from [`connectors/_template/`](connectors/_template/) and include a `SKILL.md` plus only the code and references it needs. Keep the connector easy to audit and follow the upstream MIT license notice in [`connectors/LICENSE`](connectors/LICENSE).

Every connector must document:

- Purpose and exact capabilities, grounded in the provider's public API documentation.
- Authentication method, required scopes, and allowed hosts.
- Exact CLI commands and examples; undocumented commands are out of scope.
- Read versus write behavior, with confirmation before consequential writes.
- A `## Files` manifest that lists every file the skill needs.
- A `## Maturity` label. Keep it `Draft` until live-tested against the real API.

Do not commit secrets, accept credentials through command-line arguments, or make network requests to hosts outside the documented allowlist. Do not bypass provider access controls or unsupported API use.

## Review checklist for connector pull requests

- [ ] Public API source and source date are included.
- [ ] `Auth` lists scopes, allowed hosts, and a status-check command.
- [ ] Writes and other external effects require explicit confirmation.
- [ ] `Files` manifest exactly matches the connector's required files.
- [ ] `Maturity` reflects what was actually tested.
- [ ] No credentials, private data, or unsupported access method is included.
- [ ] The catalog index links to the connector and summarizes its documented use.

## Add a template

Create one Markdown file under `templates/` with:

```markdown
# Template name

**Category:** Personal / Research / Operations / ...<br>
**Integrations:** Muse, [connected app names]<br>
**Approval level:** Low / Medium / High

## Use it for

One sentence describing the outcome.

## Prompt

> The full copy-paste prompt.

## First supervised run

Describe a small, reversible test.
```

Keep prompts specific. A good template tells Muse what to gather, what to produce, what it may do, what always needs approval, and when to stop.

## Quality rules

- Prefer a narrow workflow with a verifiable finish line.
- Include the required integrations and a fallback when one is unavailable.
- Require approval before sending, buying, deleting, publishing, submitting, or changing permissions.
- Ask the bot to cite sources or link to the records it used when practical.
- Do not include secrets, private data, or credentials.
- Link to the original creator or source when adapting an existing prompt.
- Use neutral language and avoid unsupported claims about Muse capabilities.
- Add the template to the correct README category and keep entries alphabetized within that category.

## Review checklist

- [ ] The prompt is copy-paste ready.
- [ ] Bracketed setup fields are clear.
- [ ] Integrations are named.
- [ ] Approval boundaries are explicit.
- [ ] A reversible first test is included.
- [ ] Sources and attribution are present.
- [ ] The README link works.

## Reporting problems

Open an issue with the template name, the expected behavior, the observed behavior, and a redacted example. Never include credentials, private messages, or personal customer data.
