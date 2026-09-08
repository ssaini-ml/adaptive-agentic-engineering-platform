# V0.1 Technical Closure Record

Date: 2026-09-08
Base commit: `a722a78`
Candidate status: **AUTOMATED GATES PASS — RELEASE CORPUS AND HUMAN REVIEW PENDING**

## Observed verification

| Gate | Result |
|---|---|
| Ruff over `backend`, `tests`, and release-gate code | PASS |
| Pytest | PASS — 150 tests |
| Milestone 0 evaluation foundation | PASS — 4 fixtures |
| Milestone 2A language profiling | PASS — 4 fixtures |
| Milestone 2B Python extraction | PASS — 3 structural fixtures |
| Milestones 3A/3B exact and graph retrieval | PASS — 3 exact and 4 graph cases |
| Milestone 3C PostgreSQL full text | PASS — 6 cases on PostgreSQL 16 |
| Milestone 4 grounded Q&A | PASS — 12 questions |
| Complete release-evidence checker | Expected FAIL — named release evidence remains pending |

The local verification used Python 3.13.5, which satisfies the declared Python
3.12+ requirement. CI remains pinned to Python 3.12. PostgreSQL ran from the
project's `postgres:16-alpine` Compose service on host port 5433 because another
local service occupied 5432.

Pytest emitted two dependency deprecation warnings from Starlette/FastAPI test
infrastructure; no project test failed.

## Closure changes

- The repository operating contract now records the current delivery and
  authority boundaries.
- A lightweight L2 development layer records knowledge routing, workflow state,
  runtime limits, and material decisions without replacing product contracts.
- CI now runs Ruff and the Milestone 4 evaluator in addition to prior gates.
- The tag-time release check validates technical baselines, release-scale fixture
  counts, distinct human reviewers, agreement and adjudication, reviewed fixture
  versions, holdout provenance/result, and final approval.
- M4 profile schemas now match the normative wrapper and output contracts.
- Disabled profile contracts expose explicit network, side-effect, approval, and
  payload boundaries.
- The model gateway fails closed on disabled profiles, schema/hash mismatch,
  incomplete payloads, or missing passing gate evidence references.
- `GET /review/ui` provides a no-store local visual projection of the JSON review
  queues and appends task feedback through the existing immutable feedback path.
- The PostgreSQL host port is configurable without disturbing unrelated local
  services.

## Intentionally pending

```text
development_fixture_scale: PENDING_TARGET_EXPANSION
human_label_review: PENDING_HUMAN_REVIEW
holdout_selection: PENDING
holdout_evaluation: PENDING
v0_1_release_approval: PENDING
repository_analyst_activation: DISABLED
evidence_reviewer_activation: DISABLED
```

The independent review procedure is defined in `HUMAN_REVIEW_GUIDE.md`. Fixture
owners must expand and freeze the candidate corpora before asking reviewers to
perform the final independent pass. This record supports beginning V0.2
engineering after the closure changes are reviewed and committed, but it is not
a V0.1 release report.
