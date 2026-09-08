# Adaptive Agentic Engineering Platform

An evidence-first engineering control layer that builds a reproducible
understanding of a software repository before any coding agent is allowed to
modify it.

The core principle is:

> Model intelligence is rented. Engineering intelligence is accumulated.

## Current status

The automated V0.1 closure record is available at
[`evaluation/V0_1_TECHNICAL_CLOSURE.md`](evaluation/V0_1_TECHNICAL_CLOSURE.md).
It is a technical-candidate record; development-fixture expansion, independent
label review, holdout evaluation, and human release approval remain pending.

| Milestone | Status |
|---|---|
| Milestone 0 — Evaluation foundation | Technical implementation complete |
| Human label review | Pending |
| Holdout repository selection | Pending |
| Milestone 1 — Persistent immutable scans | Complete (20 tests passed) |
| Milestone 2A — Language profiling + adapter framework | Complete (33 tests; 6 gates pass) |
| Milestone 2B — Python evidence extraction | Complete (39 tests; 11 gates pass) |
| Milestone 2C — Agent roster and orchestration specification | Complete (design only) |
| Milestone 3A — Exact structural retrieval | Complete (part of 18 M3A/M3B gates passing) |
| Milestone 3B — Bounded graph traversal | Complete (part of 18 M3A/M3B gates passing) |
| Milestone 3C — PostgreSQL full-text retrieval | Complete (22 technical gates passing) |
| Milestone 4A — Deterministic assembly and grounded Q&A | Complete (12/12 golden questions) |
| Milestone 4B/4C — Model Analyst/Reviewer activation | Disabled pending provider gates and real human holdout review |

The current implementation does not modify target repositories. It profiles
single-language, polyglot, and unknown repositories, then safely parses Python
without importing or executing repository code. Symbols, imports, inheritance,
re-exports, unresolved references, and FastAPI routes are persisted against the
immutable scan. Detected languages without an approved adapter remain explicitly
`UNSUPPORTED`. Exact symbol lookup and cycle-safe graph traversal now expose that
normalized evidence through deterministic, scan-bound APIs. PostgreSQL full-text
retrieval also indexes approved source, test, documentation, configuration, and
dependency text across every detected language, including languages whose
structural adapters are not yet available.

## Repository-language support

The platform backend uses Python, but repositories being evaluated will not be
limited to Python. V0.1 implements the Python analysis adapter first. The
evaluation core already discovers fixtures by manifest and records their
languages and evaluator profile.

Planned independently gated language packs are:

```text
Python
JavaScript
TypeScript
Java
Go
C#
Polyglot repositories
```

Each language must pass its own fixtures and holdout. A strong Python score cannot
hide a weak TypeScript or cross-language result.

## Documentation

Read the normative documentation in this order:

1. [Specification v3.5](docs/SPECIFICATION.md) — product architecture, principles,
   scope, and roadmap.
2. [V0.1 outcomes](docs/V0_1_OUTCOMES.md) — current delivery contract.
3. [Evaluation protocol](docs/EVALUATION_PROTOCOL.md) — fixtures, metrics, and
   release gates.
4. [Data model and API](docs/DATA_MODEL_AND_API.md) — persistence and HTTP
   behavior.
5. [Evaluation guide](evaluation/README.md) — fixture and runner details.
6. [Milestone 1 guide](docs/MILESTONE_1.md) — PostgreSQL, migrations, APIs, and scanning.
7. [Milestone 2A guide](docs/MILESTONE_2A.md) — automatic language profiling and coverage.
8. [Milestone 2B guide](docs/MILESTONE_2B.md) — Python evidence, APIs, and gates.
9. [Milestone 3 guide](docs/MILESTONE_3.md) — exact retrieval, graph traversal,
   APIs, limits, and gates.
10. [Milestone 3C guide](docs/MILESTONE_3C.md) — PostgreSQL lexical indexing,
    APIs, safety rules, and gates.
11. [Milestone 4 guide](docs/MILESTONE_4.md) — typed context, grounded answers,
    abstention, agent boundaries, traces, and feedback.
12. [Storage ADR](docs/adr/ADR-0001-storage.md) — PostgreSQL and future Milvus roles.
13. [Agent roster and orchestration](docs/AGENT_ROSTER_AND_ORCHESTRATION.md) —
    future roles, selection, permissions, handoffs and activation gates.

Earlier drafts are retained under `docs/archive/` and are not normative.

## Repository layout

```text
adaptive-agentic-engineering-platform/
├── backend/
│   └── adaptive_platform/
│       ├── domain/             immutable domain records
│       ├── repository/         safe local repository scanner
│       ├── database/           SQLAlchemy models and Alembic migrations
│       ├── services/           repository and scan lifecycle
│       ├── languages/          detection, profiling, and evaluation
│       ├── extraction/         language-neutral adapter contract and registry
│       ├── retrieval/          exact, graph and PostgreSQL full-text retrieval
│       ├── context/            query contracts and typed context assembly
│       ├── grounding/          deterministic claim and coverage controls
│       ├── qa/                 scan-bound question service and M4 evaluator
│       ├── agents/             disabled read-agent profiles and gateway boundary
│       ├── evaluation/         fixture validation, metrics, and runner
│       └── main.py             FastAPI application
├── docs/                       canonical specifications
├── evaluation/
│   ├── counting-rules/         versioned labelling rules
│   ├── fixtures/
│   │   ├── fx-small/
│   │   ├── fx-fastapi/
│   │   ├── fx-messy/
│   │   └── fx-polyglot/
│   ├── baselines/              generated evaluation reports
│   ├── HOLDOUT_POLICY.md
│   └── review.json             human-review status
├── tests/
├── .github/workflows/
└── pyproject.toml
```

## Requirements

- Python 3.12 or newer
- Git
- PostgreSQL 16 (Docker Compose configuration included)

Check your Python version:

```bash
python3 --version
```

On this machine, Homebrew Python can be selected explicitly:

```bash
/opt/homebrew/bin/python3 --version
```

Do not use macOS system Python 3.9 for this project.

## Installation

Open Terminal and run:

```bash
cd ~/Desktop/adaptive-agentic-engineering-platform

/opt/homebrew/bin/python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

After activation, verify:

```bash
python --version
```

The result must be Python 3.12 or newer.

## Agent roster design

Milestone 2C catalogs every system worker, control component, model agent,
sandboxed runner, and human actor from M0 through V1.0. Its canonical model-agent
roster is Repository Analyst, Evidence Reviewer, Change Planner, Implementer,
Verifier, Security Reviewer, and Repairer. A deterministic control plane will
later select the smallest compatible subset for each task from its scan, language
coverage, scope, risk, and required checks.

The document separately maps the repository evidence graph, orchestration
workflow graph, and trace causality graph. Implemented M0–2B nodes are linked to
their current code; planned nodes declare when they become active.

This is a specification milestone. Write-capable profiles remain disabled until
the V0.6 execution-control gates pass and V0.7 activates constrained coding
agents. See the [agent roster specification](docs/AGENT_ROSTER_AND_ORCHESTRATION.md).

Milestones 3A and 3B activate `RETRIEVE_EXACT` and `RETRIEVE_GRAPH` as
deterministic system workers. They are future tools for the read-only Repository
Analyst; they do not activate a coding agent or grant repository write access.

## Run Milestone 0

With the virtual environment active:

```bash
python -m adaptive_platform.evaluation.runner
```

Expected output:

```text
validated 4 fixtures; technical_status=PASS; human_review=PENDING_HUMAN_REVIEW
```

The runner writes:

```text
evaluation/baselines/milestone0.json
evaluation/baselines/milestone0.trace.jsonl
```

The baseline report contains:

- fixture versions and fingerprints,
- file and label counts,
- answerable and unanswerable question counts,
- technical integrity status,
- human-review status,
- holdout status, and
- the status of future V0.1 product gates.

The JSONL trace records evaluation execution, each fixture verification, skipped
product gates and completion. See [the trace guide](traces/README.md) and
[trace schema](traces/trace-event.schema.json).

## Run Milestone 2A

Run the automatic repository-language evaluation:

```bash
python -m adaptive_platform.languages.evaluation
```

Expected output:

```text
evaluated 4 fixtures; technical_status=PASS; human_review=PENDING_HUMAN_REVIEW
```

The report and correlated trace are written to:

```text
evaluation/baselines/milestone2a.json
evaluation/baselines/milestone2a.trace.jsonl
```

## Run Milestone 2B

Generate Python structural predictions and evaluate them against the golden
fixtures:

```bash
python -m adaptive_platform.extraction.evaluation
```

Expected output:

```text
evaluated 3 structural fixtures; technical_status=PASS; human_review=PENDING_HUMAN_REVIEW
```

The command writes normalized predictions under `evaluation/predictions/` plus
`evaluation/baselines/milestone2b.json` and its correlated JSONL trace.

## Run Milestones 3A and 3B

Run the exact-lookup and bounded graph-traversal evaluation:

```bash
make evaluate-3ab
```

Equivalent direct command:

```bash
PYTHONPATH=backend python -m adaptive_platform.retrieval.evaluation
```

Expected artifacts:

```text
evaluation/baselines/milestone3ab.json
evaluation/baselines/milestone3ab.trace.jsonl
```

The evaluator covers case-sensitive exact names, combined filters, repository
and scan isolation, deterministic ordering, incoming/outgoing/both traversal,
cycles, maximum depth 3, maximum 500 relationships, and unresolved targets. See
the [Milestone 3 guide](docs/MILESTONE_3.md) for API examples and exact behavior.

Run every maintained check in one command:

```bash
make verify
```

## Run Milestone 3C

M3C requires PostgreSQL because its release gate verifies a native `tsvector`,
GIN index, ranking, and immutability trigger:

```bash
make db-up
make migrate
make evaluate-3c
```

Expected output:

```text
evaluated 6 PostgreSQL full-text cases; technical_status=PASS; human_review=PENDING_HUMAN_REVIEW
```

The evaluator writes `evaluation/baselines/milestone3c.json` and a correlated
JSONL trace. It runs fixture data inside a rollback-only transaction. See the
[M3C implementation guide](docs/MILESTONE_3C.md) for the endpoint, filters,
chunk limits, language-neutral behavior, and safety policy.

## Decision and correction traces

The platform records observable LLM decisions and human corrections without
storing hidden chain-of-thought. A correction links to its target using
`correction_of`; revised decisions and verification events share a correlation
ID. Initial project decisions are recorded in
[traces/design-history.jsonl](traces/design-history.jsonl).

`PENDING_HUMAN_REVIEW` is expected. The provisional labels require independent
review by two engineers before V0.1 release sign-off.

Successful M3A/M3B API requests also write PostgreSQL runtime trace events:
`exact_symbol_retrieval_completed` and `graph_traversal_completed`. The exact
event stores a query hash rather than the raw query; both events store bounded
filters/counts and evidence references. These runtime events are separate from
the M3A/M3B evaluator JSONL trace.

M3C scan indexing writes `context_documents_created`; successful lexical API
requests write `full_text_retrieval_completed`. The query is represented in the
runtime trace only by SHA-256, while returned context-document references and
bounded filters remain auditable.

## Run Milestone 4

Run the deterministic grounded-Q&A evaluation:

```bash
make evaluate-4
```

Expected output:

```text
evaluated 12 M4 questions; technical_status=PASS; human_review=PENDING_HUMAN_REVIEW
```

Question tasks expose their immutable answer at `GET /tasks/{task_id}` and their
complete decision trace at `GET /tasks/{task_id}/trace`. Human corrections are
appended with `POST /tasks/{task_id}/feedback`. The Repository Analyst and
Evidence Reviewer profiles are visible at `GET /agent-profiles`, but remain
disabled until real holdout and provider-specific gates pass. `GET /review`
returns the abstention and unresolved-reference queues, and `GET /review/ui`
provides their small local visual review surface. See the
[Milestone 4 guide](docs/MILESTONE_4.md).

## Run tests

Run the complete test suite:

```bash
pytest
```

Run only evaluation tests:

```bash
pytest tests/test_evaluation_metrics.py tests/test_evaluation_fixtures.py
```

Generate a coverage report:

```bash
pytest --cov=adaptive_platform --cov-report=term-missing
```

## Run the API

Start the development server:

```bash
uvicorn adaptive_platform.main:app --app-dir backend --reload
```

Open:

```text
Health:   http://127.0.0.1:8000/health
OpenAPI:  http://127.0.0.1:8000/docs
```

The health response is:

```json
{
  "status": "ok"
}
```

Repository registration and asynchronous scan endpoints are available. See
[the Milestone 1 guide](docs/MILESTONE_1.md) for setup and example requests.

## How the evaluation system works

Milestone 0 establishes this flow:

```text
Synthetic fixture repository
          │
          ├── manifest.json
          │     version, purpose, fingerprint, label status
          │
          └── golden.json
                expected symbols, imports, routes,
                questions, claims, and resources
                         │
                         ▼
                 Evaluation runner
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
      Integrity validation      Product comparison
       available now            Milestone 2 onward
```

### Development fixtures

`fx-small` provides compact and exhaustively inspectable Python examples.

`fx-fastapi` provides routes, dependency injection, services, models, and tests.

`fx-messy` provides aliases, re-exports, nested functions, conditional imports,
decorators, and a dynamic import that cannot be statically resolved.

`fx-polyglot` provides Python, TypeScript, and Go, including generated and
vendored code. It verifies minority-language detection and explicit unsupported
extractor coverage.

Synthetic fixtures are pinned by fixture version and SHA-256 content fingerprint.
They are ordinary directories rather than nested Git repositories, preventing
them from becoming broken submodules when this project is committed.

### Golden labels

Each fixture's `golden.json` defines expected:

```text
symbols
imports
routes
re-exports
unresolved references
answerable questions
unsupported questions
required context slots
essential claims
expected resources
language profile and per-file language labels
generated and vendored classifications
expected extractor coverage
```

The rules defining what counts as a symbol or import are in
[evaluation/counting-rules/v1.md](evaluation/counting-rules/v1.md).

## Evaluating extractor output

Milestone 2B produces prediction files:

```text
evaluation/predictions/
├── fx-small.json
├── fx-fastapi.json
└── fx-messy.json
```

Each prediction file will contain:

```json
{
  "symbols": [],
  "imports": [],
  "routes": []
}
```

Run the comparison with:

```bash
python -m adaptive_platform.evaluation.runner \
  --actual-dir evaluation/predictions \
  --output evaluation/baselines/product.json
```

The resulting report will calculate symbol, import, and route precision and
recall for each fixture.

Prediction generation is implemented by the Python AST adapter. The generic
comparison runner remains available for predictions produced by future language
adapters.

## Current release gates

V0.1 targets include:

```text
symbol precision             >= 0.95
symbol recall                >= 0.95 on fx-small
import-edge recall           >= 0.90
language-file precision      >= 0.99
language-file recall         >= 0.99
extractor-routing accuracy   = 1.00
unsupported reporting recall = 1.00
citation validity            = 1.00
claim linkage                = 1.00
false-confident answer rate  <= 0.02
qualifier preservation       = 1.00
context-cache determinism    = 1.00
```

See [the evaluation protocol](docs/EVALUATION_PROTOCOL.md) for exact denominators
and counting rules.

The current fixture implementations are compact seeds. They must be expanded
toward the documented target sizes before the V0.1 release candidate.

## Human review

Milestone 0 intentionally does not fabricate review results.

Before V0.1 release sign-off:

1. Two engineers independently review the provisional fixture labels.
2. Disagreements are adjudicated.
3. Agreement metrics are recorded in `evaluation/review.json`.
4. Exact reviewed fixture versions and adjudication are recorded.
5. A licensed holdout repository is selected and labelled.
6. The release candidate is evaluated against the holdout.
7. A named human records final approval and `make release-check` passes.

## Security principles

Repository scanning must:

- never import or execute repository code,
- never run repository-provided commands,
- never install target-repository dependencies,
- enforce size, count, timeout, binary, encoding, and symlink limits,
- preserve repository boundaries,
- redact detected secrets before model context assembly, and
- bind every artifact and answer to an immutable scan.

## Troubleshooting

### `No module named adaptive_platform`

Activate the virtual environment and install the project:

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

### Python version error

Use Python 3.12 or newer:

```bash
/opt/homebrew/bin/python3 -m venv .venv
```

Then reactivate the environment.

### Evaluation reports `PENDING_HUMAN_REVIEW`

This is expected. Automated integrity checks passed, but independent human
labelling review has not been performed.

### Milestone 0 reports product metrics as `NOT_RUN`

This is expected when the generic Milestone 0 command is run without
`--actual-dir`. Run `python -m adaptive_platform.extraction.evaluation` for the
implemented Python structural gates.

### Fixture fingerprint mismatch

A fixture source file changed without updating its version and labels. Review the
change, update the affected golden labels, increment the fixture version, and
then deliberately update the manifest fingerprint.

## PostgreSQL and Milestone 1

Start the database and apply migrations:

```bash
docker compose up -d postgres
cp .env.example .env
alembic upgrade head
```

If local port `5432` is already occupied, set `AAEP_POSTGRES_PORT` and use the
same port in `AAEP_DATABASE_URL` before starting the service.

Edit `.env` and set `AAEP_ALLOWED_REPOSITORY_ROOTS` to the narrowest directory
the API may scan. See [the Milestone 1 guide](docs/MILESTONE_1.md) for requests.

PostgreSQL is authoritative. The `RetrievalIndex` interface allows optional
Milvus retrieval in V0.3 if it passes evaluation; Milvus will not own scans,
relationships, corrections, or traces.

## Next stage

M4A's deterministic read path is complete. Before activating the model-backed
M4B Repository Analyst or M4C Evidence Reviewer, finish independent human label
review, select the release-only holdout, and run provider-specific gates. The
next architecture milestone after that is V0.2 call/reference resolution and
impact analysis. Semantic embeddings remain deferred to V0.3, and coding agents
remain deferred to V0.7.
