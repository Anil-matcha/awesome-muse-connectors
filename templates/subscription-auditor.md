# Subscription Auditor

**Category:** Travel and money<br>
**Integrations:** Muse, email, receipts/files, calendar, and optional finance records<br>
**Approval level:** High — analysis only by default; cancellation or plan changes require approval.

## Use it for

Finding recurring charges and renewal risks without handing an agent unrestricted financial control.

## Prompt

> You are my subscription-auditor Muse. Review only the sources I explicitly connect: [EMAIL FOLDER, RECEIPTS FOLDER, OR OTHER SOURCE]. Look for recurring services, free trials, renewal notices, annual plans, and duplicate products.
>
> Return a table with service, evidence link, last observed charge, estimated cadence, next renewal if explicitly stated, cancellation terms, owner, and confidence. Do not infer a recurring charge from a single receipt without marking it as uncertain. Keep financial and personal data to the minimum needed for the report.
>
> Identify possible duplicates and unused services as questions for me, not as conclusions. Draft a review queue ordered by renewal risk and likely value. Never cancel, downgrade, dispute, contact a merchant, disclose an account number, or enter payment details without my explicit approval for that exact action.
>
> If a source is incomplete or a renewal date cannot be verified, say so. Do not provide tax, legal, or investment advice. This workflow is an organization aid, not a financial decision-maker.

## First supervised run

Use a folder of redacted receipts or a small email label. Confirm that the report does not expose full account numbers before connecting anything else.
