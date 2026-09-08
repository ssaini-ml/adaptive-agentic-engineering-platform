# Holdout Policy

The release-only holdout protects against tuning the platform to the three
development fixtures.

Requirements:

- 75–250 Python files at a pinned commit.
- Licence and provenance reviewed before vendoring or use.
- Contains at least one web framework, tests, relative imports, aliases and an
  intentionally unsupported question set.
- Labels are maintained separately from day-to-day feature development.
- Run only at release-candidate boundaries or approved audit points.
- Report pass/fail and regressions; do not expose detailed labels to feature
  tuning.
- Refresh after two releases or when repeated evaluation makes the fixture
  operationally familiar.

For later language packs, replace "Python files" with files in the language being
certified. Each supported language requires a holdout result. Polyglot support
additionally requires a repository containing labelled cross-language edges.

Milestone 0 establishes this policy and the holdout manifest schema. Selecting and
independently labelling the release repository requires human ownership and legal
review.

The machine-readable contract is `holdout-manifest.schema.json`.

At release time, store the reviewed manifest at `evaluation/holdout/manifest.json`
and the release-only result at `evaluation/holdout/result.json`. The manifest also
records `file_count`, `license_status`, and `provenance_status`; the result records
`fixture_id`, `technical_status`, `holdout_regression`, `evaluated_at`, and a
non-sensitive `evidence_ref`. The release-evidence workflow checks these records
without exposing detailed holdout labels.
