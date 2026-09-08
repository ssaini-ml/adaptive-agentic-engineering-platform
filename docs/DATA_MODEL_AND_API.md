# Data Model and API Contract

**Contract version 1.7**

## Status

This document is normative for V0.1 persistence and HTTP behavior. Database
migrations and generated OpenAPI must remain consistent with it.

## 1. General rules

- Primary identifiers are UUIDs.
- Stored timestamps are timezone-aware UTC.
- Repository paths are canonical absolute paths.
- User-facing source paths are repository-relative POSIX paths.
- Mutable repository registration is separate from immutable scan artifacts.
- Every evidence-bearing artifact references a scan.
- Enumerations are stored with explicit stable string values.
- JSON metadata is supplemental and must not replace queryable core fields.

## 2. SourceSpan

A source span is a reusable value object:

```text
file_id
start_line       positive, one-based
start_column     non-negative, zero-based
end_line         >= start_line
end_column       non-negative, zero-based
```

Line-only evidence may omit columns. Every stored span is validated against the
file content belonging to the same scan.

## 3. Repository

```text
id
name
canonical_path
default_branch
created_at
updated_at
```

Constraints:

```text
unique(canonical_path)
name is non-empty
```

## 4. RepositoryScan

```text
id
repository_id
commit_hash
is_dirty
working_tree_fingerprint
status
scanner_version
configuration_version
started_at
completed_at
failure_code
failure_message
file_count
total_bytes
```

Status:

```text
PENDING
RUNNING
COMPLETED
FAILED
```

A completed scan is immutable. Retry creates a new scan. Answers may reference
only completed scans.

## 5. RepositoryFile

```text
id
repository_id
scan_id
path
language
category
content_hash
size
encoding
is_generated
is_vendored
detection_signal
secret_finding_count
```

Constraints:

```text
unique(scan_id, path)
content_hash is SHA-256
size >= 0
```

Categories:

```text
SOURCE
TEST
DOCUMENTATION
CONFIGURATION
DEPENDENCY
MIGRATION
CI
API_SPECIFICATION
BUILD
OTHER
```

## 5.1 RepositoryLanguageProfile

One immutable profile belongs to one completed scan:

```text
id
scan_id
repository_type          SINGLE_LANGUAGE | POLYGLOT | UNKNOWN
primary_language         nullable
profiler_name
profiler_version
configuration_version
first_party_source_files
first_party_source_bytes
unprofiled_file_count
created_at
```

Each profile has one statistic per detected language:

```text
id
profile_id
language
source_file_count
source_bytes
source_byte_percentage
generated_file_count
generated_bytes
vendored_file_count
vendored_bytes
extractor_status         SUPPORTED | PARTIAL | UNSUPPORTED | FAILED
extractor_name           nullable
extractor_version        nullable
detection_signals        supplemental JSON
diagnostics              supplemental JSON
```

Constraints:

```text
unique(scan_id)
unique(profile_id, language)
source counts and byte counts are non-negative
percentages are between 0 and 100
primary_language references a statistic in the same profile
all counts derive only from files in profile.scan_id
```

An unsupported language remains in the profile. Absence of an extractor must not
remove files or cause the repository to be reported as single-language. Profiles
and their statistics become immutable when created for a completed scan.

## 6. Symbol

```text
id
scan_id
file_id
parent_symbol_id
name
qualified_name
symbol_type
signature
docstring
start_line
start_column
end_line
end_column
extractor_name
extractor_version
extension_metadata
```

Types:

```text
MODULE
CLASS
FUNCTION
METHOD
CONSTANT
ROUTE
MODEL
```

Constraints:

```text
unique(scan_id, file_id, qualified_name, symbol_type, start_line)
parent_symbol_id must belong to the same scan
source span must belong to file_id
```

## 7. Relationship

```text
id
scan_id
source_kind
source_id
target_kind
target_id              nullable
unresolved_target      nullable
relationship_type
resolution_status
resolution_reason      nullable
confidence
evidence_type
provenance
evidence_file_id
evidence_start_line
evidence_start_column
evidence_end_line
evidence_end_column
extractor_name
extractor_version
extension_metadata
```

Types:

```text
DEFINES
IMPORTS
REFERENCES
INHERITS
EXPOSES
TESTS
CALLS          V0.2
IMPLEMENTS     V0.2
DEPENDS_ON     V0.2
```

Resolution status:

```text
RESOLVED
PARTIALLY_RESOLVED
HEURISTIC
UNRESOLVED
AMBIGUOUS
```

Exactly one of `target_id` or `unresolved_target` is normally present.
An unresolved relationship requires `resolution_reason`.
`extension_metadata` is adapter-owned supplemental JSON; normalized fields remain
queryable columns. Both symbols and relationships become immutable when their
parent scan is completed. Migration `0003_python_evidence` creates these tables
and installs PostgreSQL enforcement triggers.

## 7.1 Structural retrieval projections

M3A/M3B retrieval does not introduce a second evidence store. It reads the
normalized records above through `StructuralRetriever` and returns immutable
response projections.

Exact symbol hit:

```text
symbol                    complete Symbol projection
file_path                 repository-relative POSIX path
```

Graph traversal response:

```text
repository_id, scan_id, start_symbol_id
direction, max_depth, count
nodes                     deterministically ordered Symbol projections
edges                     deterministically ordered TraversalEdge projections
```

TraversalEdge:

```text
relationship_id, scan_id, depth, direction
source                    Symbol projection
target                    nullable Symbol projection
unresolved_target
relationship_type, resolution_status, resolution_reason, confidence
evidence_type, provenance
evidence_file_id, evidence_file_path, evidence span
extractor_name, extractor_version, extension_metadata
```

For an unresolved relationship, `target_symbol` and `relationship.target_id`
remain null while `unresolved_target`, `resolution_status`, and
`resolution_reason` remain present. Retrieval must not synthesize a symbol.

All retrieval queries require a repository ID and completed scan ID. The service
validates repository/scan ownership before reading results. Exact lookup is
case-sensitive and compares required `query` to exact `name` or
`qualified_name`. Optional `symbol_type` values are ORed with one another; all
other supplied filters are ANDed. Graph traversal is breadth-first, cycle-safe,
and limited to `max_depth <= 3` and `limit <= 500`.

Deterministic exact ordering is:

```text
qualified_name, symbol_type, file_path, start_line, symbol_id
```

Deterministic traversal ordering begins with depth, outgoing-before-incoming
direction, relationship type, source qualified name, resolved target qualified
name or unresolved-target text, evidence file/path position, and relationship
ID. UUIDs are final tie-breakers.

Migration file `0004_structural_retrieval_indexes.py` has Alembic revision
`0004_retrieval_indexes` and adds composite indexes for:

```text
Symbol(scan_id, qualified_name)
Symbol(scan_id, name)
Symbol(scan_id, symbol_type)
Relationship(scan_id, source_id, relationship_type)
Relationship(scan_id, target_id, relationship_type)
```

These indexes do not change evidence immutability or make an external graph
database authoritative.

## 8. ContextDocument

This immutable M3C record is created and indexed before its parent scan is
sealed. PostgreSQL owns the authoritative text and native search vector; vector
embeddings remain deferred to V0.3.

```text
id
scan_id
file_id
symbol_id              nullable
document_type
content
content_hash
search_vector
metadata
start_line
end_line
```

Document types:

```text
MODULE
CLASS
FUNCTION
METHOD
TEST
DOCUMENTATION_SECTION
CONFIGURATION_SECTION
```

Constraints and policy:

```text
document_type is one of the values above
start_line >= 1 and end_line >= start_line
content_hash is SHA-256 of the bounded document content
scan_id, file_id and optional symbol_id use foreign keys
completed-scan documents are immutable in the ORM and PostgreSQL trigger
document content <= 20,000 characters and spans <= 200 lines
```

Eligible file categories are `SOURCE`, `TEST`, `DOCUMENTATION`,
`CONFIGURATION`, and `DEPENDENCY`. Generated, vendored, secret-flagged,
unsafe-path, symlink, changed, undecodable, and unapproved files do not create
documents. Source symbols additionally create linked `CLASS`, `FUNCTION`, and
`METHOD` projections where structural evidence is available.

Migration `0005_context_documents` creates the native PostgreSQL `tsvector`,
GIN index, scan/file/type indexes, and immutability trigger. The vector uses the
`simple` configuration and includes derived dotted, snake-case, path-like, and
camel-case identifier components alongside original text.

## 9. QuestionTask and Answer

QuestionTask:

```text
id
repository_id
scan_id
question
canonical_question
query_class
query_intent
status
created_at
completed_at
context_hash
cache_key
cache_status
cached_from_task_id
classifier_version
assembler_version
validator_version
failure_code
failure_message
metadata
```

`ContextPackage` stores the canonical package JSON, ordered typed slots,
unfillable gaps, assembly log, item/token counts and budgets, render strategy,
assembler version, and SHA-256 context hash. Slot status is `FILLED`,
`FILLED_EMPTY`, `AMBIGUOUS`, `UNFILLABLE`, or `OMITTED_BUDGET`.

Answer:

```text
id
task_id
answer_text
confidence
status
validator_version
gaps
response_hash
created_at
```

Answer status:

```text
ANSWERED
PARTIAL
ABSTAINED
FAILED
```

Claims are stored individually with a stable position, claim type, importance
`ESSENTIAL | OPTIONAL`, verdict, inline qualifier/check information, and typed
evidence links. Evidence link type is one of `SOURCE_SPAN`, `SYMBOL`,
`RELATIONSHIP`, `CONTEXT_DOCUMENT`, `SCAN_FACT`, `LANGUAGE_PROFILE`, or
`RETRIEVAL_RESULT`; a source file/span is required only where that reference
kind has one. Migration `0006_grounded_questions` creates these records and
PostgreSQL triggers reject updates or deletes to completed context packages,
answers, claims, and evidence links.

## 10. TraceEvent

```text
id
task_id
repository_id
scan_id
parent_event_id
correlation_id
correction_of
category
event_type
actor_type
occurred_at
duration_ms
summary
rationale_summary
input_refs
output_refs
metadata
```

Categories:

```text
REPOSITORY
RETRIEVAL
DECISION
EXECUTION
VERIFICATION
MODEL_INTERACTION
HUMAN_FEEDBACK
LEARNING
```

`correction_of` links human feedback to the event it corrects. A revised decision,
artifact changes and follow-up verification share `correlation_id`.

Model-call metadata includes provider, model, request ID, template/configuration
versions, redacted input/output hashes, tool calls, tokens, latency, cost and
status. Human-feedback metadata includes author role, channel, disposition and
changed artifacts. Metadata must not contain secrets or hidden chain-of-thought.

V0.1 uses JSONL for development traces. PostgreSQL becomes authoritative in
Milestone 1, with JSONL retained as an export format.

## 10.1 Future agent control-plane records

The following contracts are normative for V0.6+ design but are not implemented
as V0.1 database tables or HTTP endpoints. Their complete semantics are defined
in `AGENT_ROSTER_AND_ORCHESTRATION.md`.

WorkflowDefinition, NodeDefinition and EdgeDefinition:

```text
WorkflowDefinition: id, version, entry_nodes, terminal_nodes, status,
                    graph_hash, created_at

NodeDefinition: workflow_id, workflow_version, id, version, stage, kind,
                implementation_status, handler_ref, input_schema, output_schema,
                preconditions, guards, permissions, idempotency_key,
                timeout_or_budget, success_event, failure_event

EdgeDefinition: workflow_id, workflow_version, id, version, from_node, to_node,
                priority, condition_code, handoff_schema, guards,
                otherwise_edge_id, failure_transition
```

Graph constraints:

```text
workflow identity is unique by (id, version)
workflow definitions are immutable after activation
edge endpoints belong to the same workflow version
every non-terminal node has at least one declared exit edge
edge conditions and tie-breaking are deterministic
runtime node creation and undeclared transitions are forbidden
only a budgeted repair edge may form a cycle
```

AgentProfile:

```text
id
version
role
status                    ENABLED | DISABLED | RETIRED
supported_task_classes
supported_languages
required_language_coverage
capabilities
required_inputs
output_schema
permissions
budgets
required_gates
model_policy_ref
prompt_template_version
profile_hash
```

TaskRoster:

```text
id
version
task_id
repository_id
scan_id
commit_hash
working_tree_fingerprint
task_class
risk
selected_profiles
excluded_profiles
handoffs
concurrency_groups
required_approvals
resolver_version
roster_hash
supersedes_roster_id       nullable
created_at
```

AgentRun and Handoff:

```text
AgentRun: id, task_id, roster_id, profile_id, profile_version, attempt,
          status, input_hash, output_hash, started_at, completed_at,
          model_policy_ref, failure_class

Handoff: id, task_id, roster_id, producer_run_id, consumer_profile_id,
         schema_name, schema_version, scan_id, input_artifact_hashes,
         content_hash, payload_ref, created_at
```

ExecutionLease:

```text
id
repository_id
workspace_id
task_id
roster_id
contract_id
scan_id
file_paths
status                    ACTIVE | RELEASED | INVALIDATED | EXPIRED
acquired_at
expires_at
released_at
post_write_fingerprint
```

Constraints:

```text
profile identity is unique by (id, version)
rosters and handoffs are immutable after use begins
all roster artifacts reference one repository and scan
an enabled write profile requires SUPPORTED coverage for every changed language
active leases may not overlap by repository, workspace and file path
an AgentRun cannot exceed profile, contract or platform permissions
every write run requires a subsequent verification result
```

The read-only `GET /agent-profiles` list endpoint is active in M4 so operators
can verify that the two model profiles are `DISABLED`. The remaining V0.6+
control-plane endpoints are inactive in V0.1:

```http
GET  /agent-profiles/{profile_id}/versions/{version}
GET  /workflows
GET  /workflows/{workflow_id}/versions/{version}
POST /tasks/{task_id}/rosters
GET  /tasks/{task_id}/rosters/{roster_id}
GET  /tasks/{task_id}/agent-runs
GET  /tasks/{task_id}/handoffs
POST /tasks/{task_id}/approvals
```

## 11. HTTP endpoints

```http
GET  /health

POST /repositories
GET  /repositories/{repository_id}

POST /repositories/{repository_id}/scans
GET  /repositories/{repository_id}/scans
GET  /repositories/{repository_id}/scans/{scan_id}

GET  /repositories/{repository_id}/scans/{scan_id}/files
GET  /repositories/{repository_id}/scans/{scan_id}/languages
GET  /repositories/{repository_id}/scans/{scan_id}/symbols
GET  /repositories/{repository_id}/scans/{scan_id}/relationships
GET  /repositories/{repository_id}/scans/{scan_id}/retrieval/symbols
GET  /repositories/{repository_id}/scans/{scan_id}/retrieval/text
GET  /repositories/{repository_id}/scans/{scan_id}/symbols/{symbol_id}/neighbors
GET  /repositories/{repository_id}/scans/{scan_id}/overview

POST /repositories/{repository_id}/scans/{scan_id}/questions
GET  /tasks/{task_id}
GET  /tasks/{task_id}/trace
POST /tasks/{task_id}/feedback
GET  /agent-profiles
GET  /review
GET  /review/ui
```

Impact analysis is introduced in V0.2.

### 11.1 Exact symbol retrieval

```http
GET /repositories/{repository_id}/scans/{scan_id}/retrieval/symbols
    ?query=CustomerService
    &symbol_type=CLASS
    &file_path=app/services/customer.py
    &language=Python
    &limit=100
```

Parameters:

```text
query          required, non-empty, case-sensitive exact name or qualified name
symbol_type    optional, repeatable SymbolType
file_path      optional, exact repository-relative POSIX path
language       optional, exact normalized language
limit          optional integer from 1 through 500; default 20
```

An exact query with no match returns `200 OK` and an empty list. It never falls
back to case-insensitive, fuzzy, prefix, full-text, or semantic retrieval.

### 11.2 Symbol-neighbor traversal

```http
GET /repositories/{repository_id}/scans/{scan_id}/symbols/{symbol_id}/neighbors
    ?direction=BOTH
    &relationship_type=IMPORTS
    &max_depth=2
    &limit=100
```

Parameters:

```text
direction          OUTGOING | INCOMING | BOTH
relationship_type  optional, repeatable RelationshipType
max_depth           integer from 1 through 3; default 1
limit               integer from 1 through 500; default 100
```

`limit` applies to the combined traversal, including `BOTH`; it is not separately
applied per direction or depth. The response is a stable breadth-first list of
graph traversal hits. Unresolved outgoing edges may be returned but cannot be
expanded. A relationship is not rewritten when encountered from its incoming
side; `source_id` and `target_id` always retain their evidence-graph meaning.

Successful exact and graph API calls append `RETRIEVAL` trace events named
`exact_symbol_retrieval_completed` and `graph_traversal_completed`. Exact lookup
stores `query_sha256`, never the raw query. Both store normalized request bounds,
result counts, and returned symbol/relationship references with
`raw_query_retained=false`. The evaluation command writes a separate JSONL trace.

### 11.3 PostgreSQL full-text retrieval

```http
GET /repositories/{repository_id}/scans/{scan_id}/retrieval/text
    ?query=include_router%20customer_router
    &document_type=MODULE
    &category=SOURCE
    &file_path=app/main.py
    &language=Python
    &limit=20
```

Parameters:

```text
query          required searchable text, trimmed, at most 256 characters
document_type  optional, repeatable ContextDocument type
category       optional, repeatable approved RepositoryFile category
file_path      optional exact repository-relative POSIX path
language       optional exact normalized language
limit          integer from 1 through 100; default 20
```

The response is bound to `repository_id` and `scan_id` and contains
`retrieval_engine`, `count`, and deterministically ranked hits. Every hit returns
`document_id`, file/language/category fields, optional `symbol_id`, document
type, bounded content, score, content hash, line span, and supplemental metadata.
No match returns an empty list. PostgreSQL uses `websearch_to_tsquery` and
`ts_rank_cd`; stable file/span/type/UUID keys resolve score ties.

A completed scan without `context_documents_created` predates M3C and returns
`409 FULL_TEXT_INDEX_UNAVAILABLE`; it must be rescanned. This distinguishes an
unbuilt index from an indexed scan with no lexical match.

Successful calls append `full_text_retrieval_completed` with a query SHA-256,
filters, bounds, engine, result count, and context-document references. Raw query
text is not retained in the runtime trace. `SQLITE_TEST_FALLBACK` is permitted
for unit tests only and does not satisfy the M3C production gate.

## 12. Registration request

```json
{
  "path": "/workspace/example-project",
  "name": "example-project"
}
```

Response: `201 Created` with the repository resource. Registration never starts
a scan implicitly.

## 13. Scan request

```json
{
  "dirty_tree_policy": "CAPTURE",
  "configuration_version": "scanner-v1"
}
```

Policies:

```text
REJECT
CAPTURE
```

Response: `202 Accepted` with scan ID and status URL. A completed scan resource
includes commit, dirty state, fingerprint, counts, versions, and timings.

## 13.1 Language profile response

```json
{
  "scan_id": "uuid",
  "repository_type": "POLYGLOT",
  "primary_language": "TypeScript",
  "profiler_version": "language-profiler-v1",
  "languages": [
    {
      "language": "TypeScript",
      "source_file_count": 180,
      "source_bytes": 540000,
      "source_byte_percentage": 72.0,
      "extractor_status": "UNSUPPORTED"
    },
    {
      "language": "Python",
      "source_file_count": 42,
      "source_bytes": 210000,
      "source_byte_percentage": 28.0,
      "extractor_status": "SUPPORTED"
    }
  ],
  "unprofiled_files": 0
}
```

`200 OK` does not imply that every language has an extractor. Clients must use
`extractor_status` and per-language diagnostics when presenting analysis
coverage.

## 14. Question request

```json
{
  "question": "Which files import PaymentService?"
}
```

Response:

```json
{
  "task_id": "uuid",
  "scan_id": "uuid",
  "status": "ANSWERED",
  "answer": "...",
  "confidence": "DETERMINISTIC",
  "claims": [
    {
      "text": "...",
      "importance": "ESSENTIAL",
      "verdict": "SUPPORTED",
      "evidence": [
        {
          "path": "app/checkout.py",
          "start_line": 3,
          "end_line": 3
        }
      ]
    }
  ],
  "gaps": [],
  "trace_url": "/tasks/uuid/trace"
}
```

A partial answer returns supported claims plus named gaps. Abstention returns no
unsupported answer text and lists the required slots that could not be filled.
The task envelope also returns `repository_id`, `question`, `query_class`,
`query_intent`, `context_hash`, `cache_status`, typed claim evidence, and the
trace URL.

`POST /tasks/{task_id}/feedback` appends one `HUMAN_FEEDBACK` trace event. An
optional `corrected_event_id` must belong to that task and is stored as
`correction_of`. Feedback never edits a stored answer. The M4 API is local-only
and unauthenticated; it must be bound to loopback until an authentication and
authorization milestone is specified.

`GET /review` returns the local abstention and unresolved-reference queues.
Candidate rules report `DISABLED_UNTIL_V0.4`; they are not fabricated during
M4. `GET /review/ui` returns a no-store, local HTML projection that loads those
queues and can append task feedback through the existing append-only endpoint.
It is a minimal review console, not a production administration interface, and
must remain loopback-bound while the API is unauthenticated.

## 15. Errors

All errors use:

```json
{
  "error": {
    "code": "REPOSITORY_NOT_GIT",
    "message": "The path is not a Git worktree.",
    "details": {},
    "trace_id": "uuid"
  }
}
```

Required codes:

```text
PATH_NOT_ALLOWED               403
REPOSITORY_NOT_FOUND           404
REPOSITORY_NOT_READABLE        422
REPOSITORY_NOT_GIT             422
REPOSITORY_HAS_NO_HEAD         422
NO_SUPPORTED_SOURCE            422
LANGUAGE_PROFILE_UNAVAILABLE   409
NO_SUPPORTED_EXTRACTOR         422
EXTRACTOR_FAILED               500
SCAN_LIMIT_EXCEEDED            413
DIRTY_TREE_REJECTED            409
SCAN_NOT_COMPLETE              409
SCAN_REPOSITORY_MISMATCH       409
SYMBOL_NOT_FOUND               404
SCAN_NOT_COMPLETED             409
FULL_TEXT_INDEX_UNAVAILABLE    409
INVALID_RETRIEVAL_ARGUMENT     422
EVIDENCE_INTEGRITY_ERROR       500
SOURCE_SPAN_INVALID            500
TASK_NOT_FOUND                 404
TRACE_EVENT_NOT_FOUND          404
INVALID_QUERY                  422
MODEL_PROVIDER_UNAVAILABLE     503
```

## 16. Cache policy

Cache identity includes:

```text
canonical question
scan_id
working-tree fingerprint
extractor versions
classifier version
retrieval configuration
assembler version
validator version
model configuration, if used
```

Cacheable:

```text
validated ANSWERED responses
validated PARTIAL responses
deterministic coverage-gate ABSTAINED responses
```

A hit returns the original stored task and answer instead of allocating a new
task ID, then appends `cache_hit` to that task's trace. This makes the response
envelope byte-identical while preserving observable cache use.

Not cacheable:

```text
validation failures
model failures
provider failures
timeouts
cancelled tasks
```

## 17. Immutability and deletion

V0.1 does not expose artifact mutation endpoints. A new scan creates new
artifacts. Repository deletion and retention policy require a later explicit
administrative design; they are not inferred from ordinary API operations.
