# Adaptive Agentic Engineering Platform

## V0.1 — Evidence-First Repository Intelligence

---

# 1. Document Purpose

This document defines the first buildable release of the Adaptive Agentic
Engineering Platform.

The wider product vision is:

```text
Repository Intelligence
        ↓
Change Planning
        ↓
Task Contracts
        ↓
Coding Agents
        ↓
Verification
        ↓
Adaptive Repair and Learning
```

V0.1 builds the trustworthy repository-intelligence foundation required by all
later stages. It does not modify source code.

---

# 2. Product Outcome

V0.1 must prove one claim:

> Given an unfamiliar local Python Git repository, the platform can create a
> reproducible understanding of its structure, answer supported questions with
> precise evidence, and explicitly abstain when evidence is insufficient.

The output must be trustworthy enough to become input to future change planning.

---

# 3. Core Architecture

The primary architecture must NOT be:

```text
Repository → Vector Database → LLM
```

Use:

```text
                         REPOSITORY
                             │
                             ▼
                      SAFE INGESTION
                             │
                             ▼
                    IMMUTABLE SCAN
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
         STRUCTURED INDEX          RETRIEVAL INDEX
                │                         │
       files / symbols / graph     full text / chunks
       facts / relationships       optional embeddings
                │                         │
                └────────────┬────────────┘
                             ▼
                       CONTEXT ENGINE
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
     Exact Search       Graph Search      Content Search
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
                    EVIDENCE VALIDATION
                             │
                             ▼
                    SEMANTIC REASONING
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
         Repository Q&A             Impact Analysis
```

RAG is dynamic evidence retrieval. It is not repository understanding.

---

# 4. Durable Product Asset

The durable product asset is:

```text
Versioned Evidence Graph
+ Retrieval History
+ Approved Engineering Rules
+ Verification Results
+ Trace History
```

Models consume and explain this evidence. Models do not define repository truth.

---

# 5. V0.1 Scope

V0.1 includes:

```text
local Python Git repositories
safe repository validation
immutable repository scans
deterministic file inventory
Python AST extraction
symbols, imports, decorators and FastAPI routes
typed evidence-bearing relationships
exact symbol and metadata search
PostgreSQL full-text retrieval
code-aware chunks
hybrid ContextEngine
structural repository Q&A
basic reverse-dependency impact analysis
evidence validation
execution, decision and verification traces
fixture repositories and evaluation dataset
```

Semantic embeddings are optional. The product must work when they are disabled.

---

# 6. Explicit Non-Goals

Do NOT implement in V0.1:

```text
autonomous code modification
pull-request generation
deployment
multi-agent swarms
adaptive repair
automatic rule enforcement or mutation
JavaScript or TypeScript parsing
cross-repository reasoning
runtime tracing
enterprise RBAC
Kubernetes or microservices
custom foundation models or vector databases
```

These capabilities are deferred, not removed from the north-star vision.

---

# 7. Technology Stack

## Backend

```text
Python 3.12+
FastAPI
Pydantic v2
SQLAlchemy 2
Alembic
PostgreSQL
```

## Analysis

```text
pathlib
Git CLI or GitPython
Python ast
tree-sitter extension point
```

## Retrieval

```text
exact database lookup
structured metadata queries
graph traversal over PostgreSQL
PostgreSQL full-text search
pgvector as an optional extension
```

## Frontend

```text
Next.js
React
TypeScript
Tailwind CSS
```

The polished frontend begins only after evidence and retrieval quality gates pass.

---

# 8. Safety Requirements

Repository analysis must:

```text
never import repository modules
never execute repository code
never run repository-provided scripts
never install repository packages automatically
never invoke repository builds or tests automatically
never follow symlinks outside the repository
never send the entire repository to a model automatically
never send detected secrets to a model
```

The scanner must enforce file-size, file-count, total-byte, symlink, binary,
encoding, ignore, and timeout policies.

---

# 9. Repository and Scan Identity

## Repository

```text
id
name
canonical_path
default_branch
created_at
```

## RepositoryScan

An immutable analysis snapshot:

```text
id
repository_id
commit_hash
is_dirty
working_tree_fingerprint
status
scanner_version
parser_versions
started_at
completed_at
failure_reason
```

Every extracted artifact, answer, and trace must reference `scan_id`.

A commit hash alone is insufficient for a dirty working tree. The system must
capture content hashes for the snapshot or reject it explicitly.

---

# 10. Evidence Taxonomy

Do not merge facts, relationships, inference, and policy.

```text
SYNTAX_FACT
STATICALLY_RESOLVED_RELATIONSHIP
HEURISTIC_RELATIONSHIP
SEMANTIC_INFERENCE
HUMAN_APPROVED_RULE
RUNTIME_OBSERVATION          future
```

Examples:

```text
"checkout.py contains an import of PaymentService"
→ SYNTAX_FACT

"CheckoutService statically references PaymentService"
→ STATICALLY_RESOLVED_RELATIONSHIP

"the repository appears to use layered architecture"
→ SEMANTIC_INFERENCE

"controllers must not access repositories directly"
→ HUMAN_APPROVED_RULE
```

Deterministic extraction is reproducible. It is not automatically runtime truth.

---

# 11. Core Domain Objects

## RepositoryFile

```text
id
scan_id
path
language
category
content_hash
size
encoding
is_generated
```

## Symbol

Types:

```text
MODULE
CLASS
FUNCTION
METHOD
CONSTANT
ROUTE
```

Fields:

```text
id
scan_id
file_id
name
qualified_name
symbol_type
start_line
end_line
signature
docstring
extractor_name
extractor_version
```

## Relationship

Initial types:

```text
DEFINES
IMPORTS
REFERENCES
CALLS
INHERITS
TESTS
EXPOSES
```

Fields:

```text
id
scan_id
source_kind / source_id
target_kind / target_id
unresolved_target
relationship_type
resolution_status
confidence
extractor_name / extractor_version
evidence_file_id
evidence_start_line / evidence_end_line
```

## ContextChunk

```text
id
scan_id
file_id
symbol_id
chunk_type
content
content_hash
search_vector
embedding             optional
metadata
```

## TraceEvent

```text
id
task_id
scan_id
parent_event_id
event_type
category
timestamp
duration_ms
metadata
```

---

# 12. Repository Ingestion

Endpoint:

```http
POST /repositories
```

Input:

```json
{
  "path": "/workspace/example-project"
}
```

Validate:

```text
path exists and resolves to an allowed location
path is readable
path is a Git worktree
Git HEAD is resolvable
repository contains supported source
configured limits are not exceeded
```

Registration and scanning must remain separate operations.

---

# 13. Scan Pipeline

```text
1 validate repository
2 capture Git and working-tree identity
3 discover and classify files
4 hash content
5 extract Python symbols
6 extract imports, decorators and routes
7 resolve supported relationships
8 create code-aware chunks
9 build exact and full-text indexes
10 persist scan summary
11 verify consistency
12 finalize immutable scan
```

Each stage produces execution and verification trace events.

---

# 14. Python Extraction

Use Python AST to extract:

```text
modules
classes
functions and async functions
methods
constants
imports
decorators
type annotations
signatures
docstrings
FastAPI routes
```

LLMs must not perform basic symbol extraction. Every artifact must include a
valid source location and extractor version.

Relationship resolution must prefer precision over apparent completeness.

```text
RESOLVED
PARTIALLY_RESOLVED
UNRESOLVED
AMBIGUOUS
```

Dynamic imports, dependency injection, factories, aliases, decorators, and
monkey-patching must not be represented as certain runtime calls without evidence.
Unresolved targets should be retained as uncertainty signals.

---

# 15. Code-Aware Chunking

Do not use arbitrary fixed-size chunks as the primary source-code strategy.

Chunk by:

```text
module
class
function
method
test
documentation section
configuration section
```

Every chunk must include scan, commit, path, symbol, language, type, content hash,
and line-range metadata.

---

# 16. Retrieval Strategy

Use this priority:

```text
1 exact symbol lookup
2 structured metadata filtering
3 graph traversal
4 PostgreSQL full-text search
5 vector semantic retrieval, when enabled
```

Exact and full-text retrieval establish the baseline. Embeddings join the critical
path only after demonstrating measurable evaluation improvement.

Every retrieved artifact must state why it was selected.

---

# 17. Query Classification

```text
DEFINITION
REFERENCE
STRUCTURAL
TEST_COVERAGE
IMPLEMENTATION_LOCATION
IMPACT
SEMANTIC
GENERAL
```

Examples:

```text
"Where is PaymentService defined?" → DEFINITION
"What imports PaymentService?" → REFERENCE
"What could break if PaymentService changes?" → IMPACT
"Why is payment retry implemented this way?" → SEMANTIC
```

Classification must support fallback when initial retrieval is inadequate.

---

# 18. Context Engine

```python
class ContextEngine:

    async def build_context(
        self,
        scan_id,
        query,
        task_type,
    ) -> ContextPackage:
        ...
```

The engine assembles the minimum trustworthy context required. It must not send
large repository contents to a model automatically.

```json
{
  "scan_id": "...",
  "query": "...",
  "query_type": "IMPACT",
  "facts": [],
  "relationships": [],
  "retrieved_chunks": [],
  "rules": [],
  "uncertainties": [],
  "retrieval_trace": []
}
```

---

# 19. Repository Q&A

Endpoint:

```http
POST /repositories/{repository_id}/questions
```

Flow:

```text
question
   ↓
classification
   ↓
structured, graph and content retrieval
   ↓
context assembly
   ↓
optional model reasoning
   ↓
evidence validation
   ↓
answer or abstention
```

Response:

```json
{
  "scan_id": "...",
  "answer": "...",
  "confidence": "HIGH",
  "claims": [],
  "evidence": [
    {
      "path": "app/auth/service.py",
      "start_line": 20,
      "end_line": 91
    }
  ],
  "uncertainties": [],
  "trace_id": "..."
}
```

When evidence is insufficient, state what could not be established.

---

# 20. Evidence Validation and Confidence

Before returning an answer, verify:

```text
every material claim has evidence or is labeled inference
every cited path belongs to the selected scan
every cited line range exists
the cited artifact supports the claim
facts and inferences remain separate
conflicting evidence is surfaced
uncertainties are preserved
unsupported answers become abstentions
```

Confidence is derived from evidence quality and coverage:

```text
DETERMINISTIC
HIGH
MEDIUM
LOW
INSUFFICIENT
```

It is not a model's self-reported feeling.

---

# 21. Impact Analysis

Endpoint:

```http
POST /repositories/{repository_id}/impact-analysis
```

Deterministic analysis calculates first:

```text
exact target symbols
direct reverse dependencies
resolved consumers
exposed routes
related tests
external integrations
unresolved or ambiguous references
```

A model may explain consequences but must not invent the dependency list.

---

# 22. Trace Architecture

## Execution Trace

What happened:

```text
repository validated
AST parser executed
graph queried
full-text search executed
model called
```

## Decision Trace

Why an observable platform decision occurred:

```text
graph retrieval selected because the query was classified as IMPACT
```

## Verification Trace

Why a claim was accepted, downgraded, or rejected:

```text
FastAPI accepted because dependency evidence and an application entrypoint exist
```

Do not store hidden chain-of-thought. Store observable inputs, decisions, outputs,
evidence, and verification results.

---

# 23. Required API Endpoints

```http
GET  /health
POST /repositories
POST /repositories/{id}/scans
GET  /repositories/{id}
GET  /repositories/{id}/scans
GET  /scans/{scan_id}/overview
GET  /scans/{scan_id}/files
GET  /scans/{scan_id}/symbols
GET  /scans/{scan_id}/relationships
POST /repositories/{id}/questions
POST /repositories/{id}/impact-analysis
GET  /tasks/{task_id}/trace
```

Component and rule-approval endpoints arrive after the core quality gates pass.

---

# 24. Model Provider Interface

Vendor SDK calls must not spread through application logic.

```python
class ModelProvider:

    async def structured_generate(self, prompt: str, schema: type):
        ...

    async def reason(self, context, question: str):
        ...
```

Track provider, model, input hash, output schema, tokens, latency, cost, and status.
Do not store credentials or raw secrets.

---

# 25. Testing and Evaluation

Create:

```text
fixture_python_basic
fixture_python_layered
fixture_fastapi
```

Include:

```text
aliased and relative imports
duplicate symbol names
nested functions
decorated routes
dependency injection
unresolved imports
tests referencing production symbols
dirty working-tree changes
deleted and renamed files
```

Golden questions:

```text
Where is the application entrypoint?
Where is PaymentService defined?
What imports PaymentService?
Which routes expose authentication?
Which tests reference CheckoutService?
What directly depends on CustomerRepository?
What cannot be determined statically?
```

Include deliberately unanswerable questions to measure correct abstention.

---

# 26. Quality Gates

V0.1 must achieve:

```text
>= 95% symbol extraction precision on controlled fixtures
>= 90% expected import-edge recall
0 citations to nonexistent source locations
0 citations to artifacts from the wrong scan
100% of material claims linked to evidence or labeled inference
explicit abstention for unanswerable golden questions
deterministic indexes for identical content and extractor versions
incremental rescans limited to changed and affected artifacts
```

Before Q&A is declared complete, establish targets for repository size, scan time,
query latency, context size, token cost, unsupported claims, and impact accuracy.

---

# 27. Delivery Milestones

## Milestone 0 — Evaluation Foundation

```text
fixture repositories
golden extracted artifacts
golden questions
evaluation runner
baseline report
```

Exit: every future extraction and retrieval change can be measured automatically.

## Milestone 1 — Safe Repository Inventory

```text
repository validation
immutable scan identity
file discovery and classification
content hashing
Git commit and dirty-state capture
scan trace
```

Exit: an unfamiliar repository produces a reproducible inventory without executing
code.

## Milestone 2 — Python Evidence Graph

```text
AST parser
symbols and imports
decorators and FastAPI routes
typed relationships
unresolved-reference records
forward and reverse traversal
```

Exit: golden symbol and import quality gates pass.

## Milestone 3 — Structural Repository Q&A

```text
exact and metadata lookup
full-text retrieval
query classification
ContextEngine
evidence validator
answers and abstentions
retrieval and verification traces
```

Exit: golden structural questions pass with valid citations.

## Milestone 4 — Impact Analysis

```text
reverse traversal
affected routes
test association
uncertainty propagation
risk summary
```

Exit: fixture impact scenarios meet precision and recall targets.

## Milestone 5 — Semantic Retrieval

```text
provider-independent embeddings
pgvector storage
hybrid ranking
semantic retrieval trace
```

Exit: measurable improvement over exact, graph, and full-text retrieval.

## Milestone 6 — Engineering Context

```text
component discovery
domain grouping
architecture inference
measurable pattern observations
candidate rules and human approval
```

Exit: inferences retain evidence, confidence, and uncertainty.

## Milestone 7 — Repository MRI

Display repository and scan identity, stack, entrypoints, files, symbols, routes,
relationships, tests, external systems, uncertainties, and trace timeline.

---

# 28. First Demonstration

Use a small unfamiliar Python/FastAPI repository.

Display:

```text
scan identity and commit
dirty state
language and framework evidence
file and symbol counts
routes and relationships
tests
unresolved references
```

Ask:

> Where is authentication implemented?

> What references CustomerService?

> What could be affected if CustomerService's interface changes?

Then ask a deliberately unanswerable question. Supported answers must include
evidence and reproducible traces. The unsupported question must produce an
explicit abstention.

Finally, modify one file, rescan, show targeted invalidation, and prove that old
answers remain bound to the old scan.

---

# 29. Definition of Done

V0.1 is complete when an unseen Python repository can be supplied and the system
can automatically:

```text
validate the repository safely
create an immutable scan
inventory and hash relevant files
extract Python symbols, imports, decorators and routes
build evidence-bearing relationships
retain unresolved relationships
create code-aware chunks
answer defined structural questions
perform basic reverse-dependency impact analysis
return precise source evidence
abstain when evidence is insufficient
show execution, retrieval and verification traces
distinguish facts, relationships, inference and policy
incrementally update changed artifacts
pass all evaluation gates
```

No repository-specific manual configuration should be required for basic analysis.

---

# 30. Future Extension Interfaces

Do not implement these in V0.1:

```python
class ChangePlanner:

    async def plan(self, request, context):
        ...


class CodingAgent:

    async def implement(self, task, context, contract):
        ...
```

Future contracts combine repository facts, approved engineering rules, change
plans, and task requirements. Missing decisions must surface as assumptions or
blockers.

---

# 31. North-Star Architecture

```text
                          REPOSITORY
                              │
                              ▼
                   VERSIONED EVIDENCE GRAPH
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
            GRAPH         RETRIEVAL        RULES
               │              │              │
               └──────────────┼──────────────┘
                              ▼
                       CONTEXT ENGINE
                              │
                              ▼
                    EVIDENCE VALIDATION
                              │
                              ▼
                      SEMANTIC REASONING
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
              Q&A          IMPACT           PLAN
                                               │
                                               ▼
                                            CONTRACT
                                               │
                                               ▼
                                             AGENT
                                               │
                                               ▼
                                          VERIFICATION
                                               │
                                     ┌─────────┴─────────┐
                                     ▼                   ▼
                                   PASS                 FAIL
                                     │                   │
                                     ▼                   ▼
                                    PR               ADAPTATION
                                                         │
                                                         ▼
                                                     LEARNING
```

The platform should not make unsupported answers sound intelligent. It should
make engineering claims inspectable, reproducible, and safe for automated work.

