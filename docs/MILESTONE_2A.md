# Milestone 2A — Automatic Repository Language Profiling

## Delivered

- deterministic extension, filename, and shebang detection
- automatic `SINGLE_LANGUAGE`, `POLYGLOT`, and `UNKNOWN` classification
- primary-language selection using first-party source bytes
- generated and vendored code excluded from primary-language totals
- per-language file, byte, percentage, signal, and coverage statistics
- language-neutral `ExtractorAdapter` protocol and registry
- an initially honest Python `PARTIAL` status, superseded by 2B's `SUPPORTED` extractor
- explicit `UNSUPPORTED` status for detected languages without adapters
- immutable PostgreSQL language profile and statistic records
- Alembic migration `0002_language_profiles`
- `GET /repositories/{repository_id}/scans/{scan_id}/languages`
- Python, TypeScript, and Go polyglot evaluation fixture
- executable language-profile gates and correlated JSONL trace

Verification completed with 33 automated tests, all six language-profile gates,
fresh and Milestone-1 SQLite migration paths, and PostgreSQL trigger checks.

The profiler does not execute, import, build, or install repository code.

## Run

Apply the database migration:

```bash
alembic upgrade head
```

Run the evaluation:

```bash
python -m adaptive_platform.languages.evaluation
```

Run the API:

```bash
uvicorn adaptive_platform.main:app --app-dir backend --reload
```

After registering and scanning a repository:

```bash
curl http://127.0.0.1:8000/repositories/REPOSITORY_ID/scans/SCAN_ID/languages
```

## Coverage semantics

```text
SUPPORTED    approved adapter implements the declared evidence contract
PARTIAL      an adapter exists but does not yet implement the complete contract
UNSUPPORTED  the language was detected but no approved adapter exists
FAILED       the selected adapter attempted extraction and failed
```

At the 2A boundary, the Python adapter was a `PARTIAL` scaffold and did not
claim extracted evidence. Milestone 2B replaces it with the gated `SUPPORTED`
AST adapter; this paragraph records the historical 2A behavior.

## Exit condition

A scan automatically identifies all labelled languages in single-language,
polyglot, and unknown repositories; preserves generated and vendored
classification; selects registered adapters; reports unsupported coverage; and
persists the immutable profile with an auditable evaluation result.

Independent human label review and holdout selection remain pending and cannot
be replaced by the automated technical pass.
