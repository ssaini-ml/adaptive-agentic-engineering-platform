# Milestone 2B — Python Structural Evidence Extraction

## Delivered

- safe Python parsing with the standard-library AST; target code is never imported or executed
- normalized modules, classes, functions, nested functions, methods, constants, and routes
- signatures, docstrings, decorators, inheritance, imports, aliases, conditional imports, and re-exports
- deterministic FastAPI and APIRouter route detection, including router prefixes
- explicit unresolved evidence for dynamic imports and missing local or external targets
- source spans, extractor identity/version, confidence, evidence type, provenance, and extension metadata
- SHA-256 verification when inventoried source is re-read for extraction
- language-neutral immutable `symbols` and `relationships` tables
- PostgreSQL and ORM guards preventing evidence mutation after scan completion
- `GET /repositories/{repository_id}/scans/{scan_id}/symbols`
- `GET /repositories/{repository_id}/scans/{scan_id}/relationships`
- generated fixture predictions, structural release gates, and correlated JSONL traces
- Alembic migration `0003_python_evidence`

Python is the first supported extraction adapter, not a platform-wide language
assumption. TypeScript, Go, Java, and other adapters must emit the same normalized
contract and pass independent fixtures before their status becomes `SUPPORTED`.

## One-command verification

From the project root with the virtual environment active:

```bash
make verify
```

This runs lint, the complete test suite, Milestone 0 fixture validation,
Milestone 2A language profiling, and Milestone 2B structural extraction gates.

Individual commands remain available:

```bash
make test
make evaluate-2b
```

The 2B evaluator writes:

```text
evaluation/predictions/fx-small.json
evaluation/predictions/fx-fastapi.json
evaluation/predictions/fx-messy.json
evaluation/baselines/milestone2b.json
evaluation/baselines/milestone2b.trace.jsonl
```

Expected summary:

```text
evaluated 3 structural fixtures; technical_status=PASS; human_review=PENDING_HUMAN_REVIEW
```

## Run against a repository

Start PostgreSQL, migrate, and run the API:

```bash
make db-up
make migrate
make run
```

Set `AAEP_ALLOWED_REPOSITORY_ROOTS` in `.env` to the narrowest directory that
contains the target repository. Register it and request a scan as described in
[Milestone 1](MILESTONE_1.md). After completion:

```bash
curl http://127.0.0.1:8000/repositories/REPOSITORY_ID/scans/SCAN_ID/languages
curl http://127.0.0.1:8000/repositories/REPOSITORY_ID/scans/SCAN_ID/symbols
curl http://127.0.0.1:8000/repositories/REPOSITORY_ID/scans/SCAN_ID/relationships
```

The language response states coverage explicitly. A polyglot scan may therefore
contain `SUPPORTED` Python evidence alongside `UNSUPPORTED` TypeScript or Go
coverage; unsupported files are never silently discarded.

## Safety and uncertainty

The extractor reads only first-party inventoried `SOURCE` and `TEST` files. It
rejects symlinks, paths outside the repository, changed hashes, and decoding
failures. Syntax failures produce a `PARTIAL` extractor result with diagnostics.
Dynamic imports and targets not proven by the snapshot remain `UNRESOLVED` with
a named reason rather than being guessed.

## Exit condition

The automated development-fixture gates pass for Python symbols, imports, and
routes, and extracted evidence is scan-bound and immutable. Independent human
label review and the release-only holdout remain pending; 2B's technical pass is
not V0.1 release approval.

The Milestone 2C agent-roster design checkpoint is documented in
[Agent Roster and Orchestration](AGENT_ROSTER_AND_ORCHESTRATION.md). The next
runtime build stage remains Milestone 3: exact lookup, full-text retrieval, and
graph traversal over this evidence. It must not activate semantic embeddings or
code-writing agents.
