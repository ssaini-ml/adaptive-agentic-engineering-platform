# Milestone 3 — Structural Retrieval

**Implementation guide v1.0** · M3A exact lookup and M3B graph traversal

## Outcome

Milestones 3A and 3B expose the immutable evidence produced by Milestone 2B as
deterministic, scan-bound retrieval. Clients can find symbols by exact identity
and traverse structural relationships without a model call, embeddings, or
execution of target-repository code.

This is a language-neutral core. The current evidence happens to come from the
Python adapter, but retrieval operates only on normalized `Symbol`,
`Relationship`, `RepositoryFile`, and `RepositoryScan` records. A future
TypeScript, Go, Java, C#, or polyglot adapter can use the same service and API.

Milestone 3C—PostgreSQL full-text retrieval—is now delivered in the companion
`MILESTONE_3C.md` guide. Milvus and semantic embeddings remain deferred to V0.3
and must pass their A/B gate before admission.

## Delivered capabilities

### M3A — exact symbol lookup

`StructuralRetriever` performs a case-sensitive lookup within one completed
scan. It never falls back to fuzzy, prefix, semantic, or case-insensitive
matching. The required `query` value matches an exact `name` **or** exact
`qualified_name`. Supported inputs are:

```text
query            required exact name or qualified name
symbol_type      optional, repeatable normalized SymbolType
file_path        exact repository-relative POSIX path
language         exact normalized repository-file language
limit            1..500
```

`query` is always required. Metadata filters combine with the name match using
logical `AND`; repeatable symbol types combine with logical `OR` inside that
filter. Results use deterministic ordering:

```text
qualified_name ASC,
symbol_type ASC,
file_path ASC,
start_line ASC,
symbol_id ASC
```

The final UUID tie-breaker prevents unstable ordering when two rows otherwise
compare equally. A syntactically valid query with no match returns an empty
result, not a guessed symbol.

### M3B — bounded graph traversal

Traversal starts from a symbol that belongs to the selected repository and
scan. It supports:

```text
direction          OUTGOING | INCOMING | BOTH
relationship_type  optional, repeatable relationship-type filter
max_depth          1..3
limit              1..500
```

The traversal is breadth-first, cycle-safe, and deterministic. A symbol is
expanded at most once at its shallowest discovered depth. Relationships are
returned in a stable order by traversal depth, outgoing-before-incoming
direction, relationship type, source qualified name, target identity, evidence
position, and relationship ID. `depth` in each result is the number
of relationship hops from the requested symbol; the start symbol is depth 0 and
is not emitted as an edge.

For `BOTH`, incoming and outgoing candidates are considered in the same stable
ordering rather than concatenating two independently limited result sets. The
global `limit` applies to returned edges for the complete traversal.

Unresolved relationships remain first-class results. Their `target_id` stays
null, and their `unresolved_target`, `resolution_status`, and
`resolution_reason` are returned unchanged. They may be emitted but cannot be
expanded into another hop. The retriever never invents a target to make a path
look complete.

## Safety and consistency invariants

- The repository and scan must exist and belong to one another.
- Retrieval is allowed only for a `COMPLETED` scan.
- Every returned file, symbol, relationship, and target belongs to that scan.
- The start symbol must belong to the same repository and scan.
- Limits are validated before executing a query: exact and traversal results are
  capped at 500, and traversal depth is capped at 3.
- Traversal is read-only and does not mutate or annotate stored evidence.
- Empty results and unresolved targets remain explicit; there is no model-based
  completion or silent cross-scan fallback.
- Identical database state, inputs, and configuration produce the same ordered
  response.

## Structural indexes

Migration file `0004_structural_retrieval_indexes.py` with Alembic revision
`0004_retrieval_indexes` adds composite PostgreSQL/SQL indexes for the normalized
access paths. The indexes optimize behavior without creating a second source of
truth:

```text
symbols(scan_id, qualified_name)
symbols(scan_id, name)
symbols(scan_id, symbol_type)
relationships(scan_id, source_id, relationship_type)
relationships(scan_id, target_id, relationship_type)
```

PostgreSQL remains authoritative. The same service contract works in SQLite for
tests; database-specific query plans do not change result semantics.

## HTTP API

### Exact symbols

```http
GET /repositories/{repository_id}/scans/{scan_id}/retrieval/symbols
    ?query=app.services.customer.CustomerService
    &symbol_type=CLASS
    &language=Python
    &limit=100
```

The response envelope contains `repository_id`, `scan_id`, `query`, `count`, and
a deterministically ordered `hits` list. Each hit contains normalized symbol
fields plus its repository-relative `file_path`. Language remains an input
filter over the associated repository-file record.

Another example:

```bash
curl --get \
  'http://127.0.0.1:8000/repositories/REPOSITORY_ID/scans/SCAN_ID/retrieval/symbols' \
  --data-urlencode 'query=CustomerService' \
  --data-urlencode 'symbol_type=CLASS'
```

### Symbol neighbors

```http
GET /repositories/{repository_id}/scans/{scan_id}/symbols/{symbol_id}/neighbors
    ?direction=BOTH
    &relationship_type=IMPORTS
    &max_depth=2
    &limit=100
```

The response envelope contains `repository_id`, `scan_id`, `start_symbol_id`,
`direction`, `max_depth`, `count`, a deterministically ordered `nodes` list, and
an `edges` list. Each edge identifies its hop depth and direction relative to
the expansion that discovered it, returns relationship evidence, and includes
the source and resolved target symbol when one exists. Unresolved targets keep
their unresolved text and reason instead.

Example:

```bash
curl --get \
  'http://127.0.0.1:8000/repositories/REPOSITORY_ID/scans/SCAN_ID/symbols/SYMBOL_ID/neighbors' \
  --data-urlencode 'direction=OUTGOING' \
  --data-urlencode 'max_depth=3' \
  --data-urlencode 'limit=500'
```

Invalid enum values or limits return `422`. Repository/scan mismatch, an
incomplete scan, and a start symbol outside the selected scan use the platform's
typed error envelope rather than returning partial cross-boundary data.

The older collection endpoints remain available for inventory/debugging:

```http
GET /repositories/{repository_id}/scans/{scan_id}/symbols
GET /repositories/{repository_id}/scans/{scan_id}/relationships
```

They are not substitutes for the bounded retrieval contract.

### Runtime retrieval traces

Successful API calls append scan-bound PostgreSQL trace events:

```text
exact_symbol_retrieval_completed
graph_traversal_completed
```

The exact event records a SHA-256 digest of the query—not the raw query—plus
filters, limit, result count, and returned symbol references. The graph event
records the start symbol, direction, relationship filters, maximum depth, limit,
edge count, and returned relationship references. Both use category `RETRIEVAL`,
actor `SYSTEM`, and `raw_query_retained=false`. These runtime events are distinct
from `milestone3ab.trace.jsonl`, which records execution of the evaluation gates.

## Runtime nodes and the agent roster

M3A/M3B activate deterministic nodes, not autonomous model agents:

```text
RETRIEVE_EXACT  → exact-symbol-result-v1
RETRIEVE_GRAPH  → graph-traversal-result-v1
```

They are tools for the future read-only `REPOSITORY_ANALYST` profile. The profile
is still not an answer-producing runtime in M3A/M3B; grounded assembly, coverage
checks, and claim validation arrive in Milestone 4. Coding agents remain disabled
until their later execution-control milestones.

## Run and verify

Install and migrate once:

```bash
cd ~/Desktop/adaptive-agentic-engineering-platform
source .venv/bin/activate
make db-up
make migrate
```

Run the M3A/M3B evaluation:

```bash
make evaluate-3ab
```

Equivalent direct command:

```bash
PYTHONPATH=backend python -m adaptive_platform.retrieval.evaluation
```

Generated artifacts:

```text
evaluation/baselines/milestone3ab.json
evaluation/baselines/milestone3ab.trace.jsonl
```

Run every maintained check:

```bash
make verify
```

The M3A/M3B evaluation covers exact case sensitivity, combined filters, scan and
repository isolation, stable ordering, incoming/outgoing/both traversal,
relationship filtering, cycles, depth and result caps, and unresolved-target
preservation. Its three exact cases, four graph cases, and shared invariants
produce 18 passing technical gates. Human review and the holdout remain separate
V0.1 release gates.

## Completion boundary

M3A and M3B are complete because implementation tests, migration verification,
and the structural retrieval evaluator pass.

M3C now completes the deterministic Milestone 3 retrieval surface with bounded
PostgreSQL full-text retrieval over approved immutable documents. Next,
Milestone 4 assembles exact, graph, and full-text results into a typed context
package before any model-backed analysis is activated.
