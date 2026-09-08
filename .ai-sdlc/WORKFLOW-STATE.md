# Workflow State

Last updated: 2026-09-08

## V0.1 technical closure

Status: finalized — automated scope
Human owner: project maintainer
Source commit: `a722a78`

### In scope

- Align repository operating instructions with the current delivery boundary.
- Make CI enforce lint and every implemented milestone evaluator.
- Reconcile disabled M4 agent profile and gateway contracts with normative docs.
- Add focused adversarial boundary tests without changing provisional labels.
- Provide a minimal visual surface for existing abstention and unresolved queues.
- Run the broadest locally available verification and record unavailable gates.

### Human-owned release gates

- Development-fixture expansion toward the normative release sizes: pending;
  expanded labels must then enter independent review.
- Independent golden-label review: pending two reviewers and adjudication.
- Release-only holdout selection, licensing, labelling, and evaluation: pending.
- V0.1 human release approval: pending the preceding evidence.

### Observed validation

- Ruff: PASS.
- Pytest: PASS, 150 tests.
- Milestones 0, 2A, 2B, 3A/3B, 3C, and 4: technical PASS.
- PostgreSQL 16 migration and six-case full-text evaluation: PASS.
- Release-evidence checker: expected FAIL while corpus, human review, holdout,
  regenerated post-review baselines, and approval evidence remain pending.
- Technical closure record: `evaluation/V0_1_TECHNICAL_CLOSURE.md`.

### Activation boundary

Repository Analyst and Evidence Reviewer remain disabled. V0.2 may begin after a
reproducibly green technical closure, but no human-reviewed V0.1 release or model
profile activation may be claimed while fixture scale or human gates remain
pending.
