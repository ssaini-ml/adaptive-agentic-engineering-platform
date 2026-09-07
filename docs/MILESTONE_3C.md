# Milestone 3C — PostgreSQL Full-Text Retrieval

**Implementation guide v1.0** · bounded, scan-bound lexical evidence

## Outcome

M3C completes Milestone 3 by adding deterministic PostgreSQL full-text search
over immutable repository evidence. It complements exact symbol lookup and graph
traversal; it does not replace either one and does not call a model.

The index is language-neutral. Python, TypeScript, Go, Java, C#, documentation,
and configuration text use the same `ContextDocument` contract. A language does
not need a structural adapter to be lexically searchable.

## Indexed material

During a `RUNNING` scan, the platform reads each admitted file again, verifies
its SHA-256 inventory hash, builds context documents, populates its search
vector, and only then seals the scan. Eligible repository-file categories are:

```text
SOURCE
TEST
DOCUMENTATION
CONFIGURATION
DEPENDENCY
```

Generated, vendored, secret-flagged, unsupported-category, binary, undecodable,
unsafe-path, symlink, oversized, and content-changed material is not admitted.
Exclusion counts are recorded in the `context_documents_created` trace event.
M3C excludes an entire secret-flagged file because redaction spans are not yet a
stored scanner artifact; it never pretends that partially redacted content is
complete.

File documents use `MODULE`, `TEST`, `DOCUMENTATION_SECTION`, or
`CONFIGURATION_SECTION`. When structural evidence exists, source symbols also
produce linked `CLASS`, `FUNCTION`, or `METHOD` documents. Route documents map
to `FUNCTION` and model documents map to `CLASS` without changing the underlying
symbol type.

Documents are deterministically bounded to at most 200 lines and 20,000
characters. Each carries:

```text
document_id, scan_id, file_id, optional symbol_id
document_type
content and SHA-256 content_hash
file_path, language and repository-file category
one-based start_line and end_line
chunk and source-hash metadata
```

IDs derive from the scan, file, optional symbol, chunk, span, and content hash.
Identical scan input therefore produces identical documents.

## PostgreSQL search

PostgreSQL is the authoritative engine. Migration `0005_context_documents.py`
with revision `0005_context_documents` creates the immutable table, a native
`tsvector` column, a GIN index, scan/file/type indexes, foreign keys, checks, and
a completed-scan immutability trigger.

The vector uses PostgreSQL's `simple` configuration so code identifiers are not
stemmed or removed as natural-language stop words. Indexed text contains both
the original content and a derived identifier form that separates dotted,
snake-case, path-like, and camel-case components. Consequently searches such as
`include_router customer_router`, `CustomerService`, and
`importlib.import_module` retain useful code-level lexical matches.

Search uses `websearch_to_tsquery`, `ts_rank_cd`, and deterministic tie-breakers:

```text
score DESC
file_path ASC
start_line ASC
end_line ASC
document_type ASC
document_id ASC
```

SQLite implements an explicit `SQLITE_TEST_FALLBACK` for fast unit and API
tests. It is not the M3C production engine and cannot satisfy the PostgreSQL
release gate.

## HTTP API

```http
GET /repositories/{repository_id}/scans/{scan_id}/retrieval/text
    ?query=include_router%20customer_router
    &document_type=MODULE
    &category=SOURCE
    &language=Python
    &file_path=app/main.py
    &limit=20
```

`query` is required, trimmed, must contain searchable text, and is limited to
256 characters. `document_type` and `category` are repeatable OR filters; the
remaining filters combine with them using AND. `file_path` is an exact
repository-relative POSIX path. `limit` is `1..100`.

The response contains `repository_id`, `scan_id`, the submitted `query`,
`retrieval_engine`, `count`, and ordered hits. A hit includes its content, score,
hash, type, file/language/category metadata, optional symbol link, and resolvable
line citation. No match returns an empty list; the service does not broaden to
fuzzy or semantic retrieval.

Repository/scan mismatch, incomplete scans, invalid types/categories, excessive
queries, and excessive result limits use typed errors. Search never falls back
to another repository or scan.

Scans completed before migration to M3C have no index-build marker and return
`FULL_TEXT_INDEX_UNAVAILABLE` rather than a misleading empty result. Create a
new scan to build context documents. A marked M3C scan with no matching text
returns a legitimate empty list.

## Runtime traces

Index creation appends `context_documents_created`. Each successful search
appends `full_text_retrieval_completed` with:

```text
query SHA-256, never the raw query
document/category/path/language filters
limit and retrieval engine
result count and returned context-document references
raw_query_retained=false
```

These are operational PostgreSQL trace events. The evaluation trace in
`evaluation/baselines/milestone3c.trace.jsonl` separately records execution and
verification of the milestone gates.

## Evaluation and gates

The M3C evaluator executes inside one rollback-only PostgreSQL transaction. It
loads six labelled cases spanning Python, FastAPI, messy dynamic syntax,
TypeScript, Go, and documentation, then verifies:

- per-case file-path precision and recall;
- native PostgreSQL engine and populated vectors;
- the GIN index and database immutability trigger;
- deterministic ranking and strict scan isolation;
- query/result bounds and line-citation validity;
- generated and vendored exclusion; and
- lexical coverage for languages without structural adapters.

The six cases plus common invariants produce 22 passing technical gates. Human
label review remains `PENDING_HUMAN_REVIEW` and is not replaced by this pass.

## Run

```bash
cd ~/Desktop/adaptive-agentic-engineering-platform
source .venv/bin/activate
make db-up
make migrate
make evaluate-3c
```

Generated artifacts:

```text
evaluation/baselines/milestone3c.json
evaluation/baselines/milestone3c.trace.jsonl
```

Run every maintained gate, including PostgreSQL M3C:

```bash
make verify
```

## Agent and milestone boundary

M3C activates `BUILD_CONTEXT_DOCUMENTS` and `RETRIEVE_FULL_TEXT` as
deterministic system workers. They become tools for the future read-only
`REPOSITORY_ANALYST`; they are not model agents and receive no write authority.

Milestone 3 is now technically complete. Milestone 4 is next: query
classification, typed context assembly across exact/graph/full-text retrieval,
coverage checks, grounded analysis, claim validation, and explicit abstention.
