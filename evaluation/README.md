# Evaluation Foundation

For V0.1 release-candidate human validation, use
[`HUMAN_REVIEW_GUIDE.md`](HUMAN_REVIEW_GUIDE.md). The latest locally observed
automated closure evidence is recorded in
[`V0_1_TECHNICAL_CLOSURE.md`](V0_1_TECHNICAL_CLOSURE.md); it does not replace
independent review or holdout approval.

Milestone 0 provides the measurement system used by every later release.

The runner is language-neutral. Python structural fixtures and a Python,
TypeScript, and Go polyglot profiling fixture use the same manifest discovery,
integrity checks, normalized labels, metrics, and reports.

## Contents

```text
counting-rules/v1.md       normative label counting rules
fixtures/fx-small          compact exhaustive fixture
fixtures/fx-fastapi        framework and route fixture
fixtures/fx-messy          difficult static-analysis fixture
fixtures/fx-polyglot       minority-language and adapter-coverage fixture
HOLDOUT_POLICY.md          release-only generalisation policy
holdout-manifest.schema.json reviewed holdout-manifest contract
holdout-result.schema.json release-only result contract
review.json                review, adjudication, fixture-version, and approval status
check_review_complete.py   complete V0.1 release-evidence gate
baselines/milestone0.json  generated integrity baseline
baselines/milestone0.trace.jsonl  execution, decision and verification trace
baselines/milestone2a.json        language-profile gate report
baselines/milestone2a.trace.jsonl language-profile evaluation trace
baselines/milestone2b.json        Python structural gate report
baselines/milestone2b.trace.jsonl Python structural evaluation trace
baselines/milestone3ab.json        exact and graph retrieval gate report
baselines/milestone3ab.trace.jsonl exact and graph retrieval evaluation trace
baselines/milestone3c.json         PostgreSQL full-text retrieval gate report
baselines/milestone3c.trace.jsonl  PostgreSQL full-text evaluation trace
baselines/milestone4.json          grounded-Q&A development gate report
baselines/milestone4.trace.jsonl   grounded-Q&A evaluation trace
full-text-cases.json               labelled lexical queries, filters and expected paths
predictions/                      generated normalized extractor output
```

Synthetic development fixtures are pinned by fixture version and content
fingerprint; the parent project revision supplies their commit history without
creating nested Git repositories. External holdouts are additionally pinned to
their upstream commit. Golden labels remain provisional until two engineers
complete independent review.

## Run

```bash
python -m adaptive_platform.evaluation.runner
```

The command appends a correlated trace sequence to
`baselines/milestone0.trace.jsonl`. Use `--trace-output PATH` to select another
audit file.

To evaluate extractor predictions:

```bash
python -m adaptive_platform.evaluation.runner \
  --actual-dir evaluation/predictions \
  --output evaluation/baselines/product.json
```

Prediction files use the same top-level `symbols`, `imports`, and `routes`
arrays as each fixture's `golden.json`.

To run the implemented Milestone 2A language gates:

```bash
python -m adaptive_platform.languages.evaluation
```

This evaluates file-language detection, generated/vendor classification,
primary language, repository type, extractor routing, and explicit unsupported
language reporting. A technical pass does not replace pending human label review.

To generate Python predictions and run the Milestone 2B structural gates:

```bash
python -m adaptive_platform.extraction.evaluation
```

This evaluates only fixtures declaring `structural-v1`. The polyglot fixture uses
`language-profile-v1` and remains governed by the 2A evaluator.

To run the implemented Milestone 3A/3B retrieval gates:

```bash
python -m adaptive_platform.retrieval.evaluation
```

The retrieval evaluator is language-neutral and queries normalized persisted
evidence. It checks exact case-sensitive symbol matching, combined symbol/file/
language filters, scan isolation, stable ordering, incoming/outgoing/both graph
traversal, cycle safety, depth and result limits, and unresolved-target
preservation. Its three exact cases, four graph cases, and common invariants
currently pass all 18 technical gates. It does not invoke a model or semantic
index; independent human label review remains pending.

To run the implemented Milestone 3C PostgreSQL lexical gates:

```bash
make db-up
make migrate
make evaluate-3c
```

The evaluator requires PostgreSQL and uses a rollback-only transaction. Six
labelled Python, FastAPI, messy-syntax, TypeScript, Go, and documentation cases
plus shared invariants produce 22 technical gates. They cover native `tsvector`
search, the GIN index, code-identifier normalization, populated vectors,
deterministic ordering, scan isolation, bounds, citations, immutable documents,
generated/vendor exclusion, and languages without structural adapters. The
SQLite fallback used by unit tests does not satisfy this gate.

To run the Milestone 4 typed-assembly and grounded-Q&A gates:

```bash
python -m adaptive_platform.qa.evaluation
```

The evaluator builds isolated temporary Git repositories from every fixture,
runs the safe scanner and evidence pipeline, and checks all 12 golden questions.
It currently reports 100% query-class and slot-map accuracy, 100% answer coverage
on the answerable set, 100% abstention recall, 100% citation validity, zero
false-confident answers, and zero pre-gate model calls. SQLite is only a
disposable orchestration harness here; native PostgreSQL retrieval remains
governed by `evaluate-3c`, and migration 0006 is separately verified on
PostgreSQL.

## Adding a language pack

1. Create uniquely named small, realistic/framework, and messy fixtures.
2. Add `manifest.json` with `languages` and `evaluator_profile`.
3. Normalize common labels into `symbols`, `imports`, `routes`, and `questions`.
4. Add language-specific counting rules and adapter extensions where needed.
5. Obtain independent label review.
6. Add a licensed release-only holdout.
7. Gate and report that language separately, including mixed-language edges.

No runner code change is required merely to discover a new fixture.

## Current gate

The technical Milestone 0 foundation can pass automatically. Human agreement and
holdout selection cannot be manufactured by code and remain explicit release
sign-off tasks.

At a release boundary, run:

```bash
make release-check
```

This command intentionally fails during normal development. It passes only when
the reviewed fixture versions and statuses, release-scale corpus counts, all six
technical baseline reports, holdout manifest/result, distinct reviewers,
agreement, adjudication, and final approval are complete. A failing tag workflow
reports an invalid release candidate; repository rules and release publication
processes must also require that check because GitHub cannot retract a pushed tag.
