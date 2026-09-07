# Adaptive Agentic Engineering Platform

> Document status: North-star product and architecture specification. The complete
> vision below is intentionally broader than the first implementation milestone.

## V0.1 — Repository Intelligence, Hybrid RAG, Engineering Context and Tracing

---

# 0. Implementation Recommendation

The architectural direction in this document is accepted, with one important
delivery correction: the complete feature set is a north-star roadmap rather
than a single V0.1 release.

The first release must prove one narrow claim exceptionally well:

> Given an unfamiliar Python repository, the platform can answer supported
> structural questions with precise, commit-bound evidence and explicitly
> abstain when its evidence is insufficient.

## 0.1 Durable Product Asset

The durable asset is a versioned evidence graph whose claims can be reproduced,
challenged, and updated. Models consume this evidence; they do not define truth.

## 0.2 Evidence Taxonomy

The implementation must not treat all deterministic output as runtime truth.
Every claim must be represented as one of:

```text
SYNTAX_FACT
STATICALLY_RESOLVED_RELATIONSHIP
HEURISTIC_RELATIONSHIP
SEMANTIC_INFERENCE
HUMAN_APPROVED_RULE
RUNTIME_OBSERVATION (future)
```

For example, an AST can prove that a name is imported syntactically, but it may
not prove which runtime object is invoked through dependency injection, dynamic
imports, factories, decorators, or monkey-patching.

## 0.3 Immutable Scan Snapshots

`RepositoryScan` is a first-class domain object. Files, symbols, relationships,
chunks, questions, answers, and traces must be bound to a scan snapshot and its
Git commit. A dirty working tree must be captured with content hashes or rejected
explicitly; a commit hash alone is not sufficient.

Conceptually:

```text
Repository
  └── RepositoryScan
        ├── files
        ├── symbols
        ├── relationships
        ├── chunks
        └── derived engineering context
```

## 0.4 Typed, Provenance-Bearing Relationships

Graph relationships must have typed endpoints and retain:

```text
scan_id
source_kind / source_id
target_kind / target_id
relationship_type
resolution_status
confidence
extractor_name / extractor_version
evidence_location
```

Unresolved references should be retained as uncertainty signals rather than
silently discarded.

## 0.5 Retrieval Rollout

Exact lookup and PostgreSQL full-text search establish the measurable baseline.
Vector retrieval is additive and must demonstrate an evaluation improvement
before becoming part of the critical path. The system must remain useful with
embeddings disabled.

## 0.6 Evidence Validation

Before returning an answer, validation must verify that:

1. every material claim has evidence,
2. cited paths and line locations exist in the selected scan,
3. evidence supports the claim rather than merely mentioning its subject,
4. facts and inferences are clearly distinguished,
5. conflicting evidence and unresolved uncertainty are surfaced, and
6. the system abstains when the support threshold is not met.

## 0.7 Delivery Sequence

The approved delivery sequence is:

```text
Milestone 0: fixtures, golden questions, and evaluation harness
Milestone 1: safe Python inventory and immutable scan snapshots
Milestone 2: Python symbols, imports, routes, and evidence graph
Milestone 3: exact and full-text structural Q&A with citations
Milestone 4: reference resolution, reverse traversal, and impact analysis
Milestone 5: semantic retrieval measured against the baseline
Milestone 6: components, architecture inference, and candidate rules
Milestone 7: frontend Repository MRI and trace exploration
```

Rule discovery must initially report measurable observations, such as "17 of 18
HTTP clients specify a timeout," rather than immediately proposing universal
policy.

## 0.8 Measurable Release Gate

V0.1 is accepted only when the evaluation fixtures demonstrate:

```text
>= 95% symbol extraction precision
>= 90% expected import-edge recall
0 citations to nonexistent or stale source locations
explicit abstention for unanswerable golden questions
100% of material answer claims linked to evidence or labeled inference
deterministic structured indexes for identical inputs and extractor versions
incremental scans limited to changed files and affected derived artifacts
```

Repository-size, scan-time, query-latency, context-size, token-cost, and
unsupported-claim targets must be baselined during Milestone 1 and frozen before
Milestone 3 is declared complete.

---

# 1. Product Objective

Build the first working foundation of an Adaptive Agentic Engineering platform.

The platform must begin with a software repository and construct a machine-readable understanding of that repository before any coding agent is allowed to modify code.

V0.1 must provide:

1. repository ingestion,
2. deterministic repository scanning,
3. code symbol extraction,
4. dependency and relationship mapping,
5. structured engineering context,
6. code-aware RAG,
7. hybrid context retrieval,
8. repository Q&A,
9. change-impact analysis,
10. engineering-rule discovery,
11. structured execution, decision and verification traces.

V0.1 must NOT autonomously modify code.

The implementation must create clean extension points for:

```text
Change Planning
↓
Task Contracts
↓
Coding Agents
↓
Verification
↓
Adaptive Repair
↓
Ratchet Learning
```

---

# 2. Core Architectural Principle

The product must NOT use:

```text
Repository
↓
Vector DB
↓
LLM
```

as its primary architecture.

Use:

```text
                         REPOSITORY
                             │
                             ▼
                     DETERMINISTIC SCAN
                             │
                 ┌───────────┴───────────┐
                 ▼                       ▼
          STRUCTURED INDEX            RAG INDEX
                 │                       │
         symbols / graph          semantic chunks
         relationships            docs / code
         dependencies             tests / ADRs
                 │                       │
                 └───────────┬───────────┘
                             ▼
                       CONTEXT ENGINE
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
          Exact Search   Graph Search   RAG Search
                │            │            │
                └────────────┼────────────┘
                             ▼
                      CONTEXT ASSEMBLER
                             │
                             ▼
                    SEMANTIC REASONER
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
          Repo Q&A       Impact Analysis   Rules
```

---

# 3. Key Product Principle

RAG must be treated as:

> **dynamic evidence retrieval**

not:

> repository understanding.

Repository understanding comes from:

```text
deterministic parsing
+
relationships
+
structured context
+
validated inference
```

RAG supplements this by retrieving detailed evidence.

---

# 4. Technology Stack

## Backend

Use:

```text
Python 3.12+
FastAPI
Pydantic v2
SQLAlchemy
Alembic
PostgreSQL
```

---

## Parsing and repository analysis

Use:

```text
Python ast
tree-sitter
GitPython
pathlib
```

Add other parsers only when necessary.

---

## Retrieval

Use:

```text
PostgreSQL
PostgreSQL full-text search
pgvector
```

The application must work even if semantic retrieval is disabled.

---

## Frontend

Use:

```text
Next.js
React
TypeScript
Tailwind CSS
```

---

## LLM access

Create a provider-independent interface.

Example:

```python
class ModelProvider:

    async def structured_generate(
        self,
        prompt: str,
        schema: type
    ):
        ...

    async def reason(
        self,
        context,
        question
    ):
        ...
```

Do not spread vendor-specific SDK calls through application logic.

---

# 5. Core Domain Objects

Implement these domain objects.

## Repository

```text
Repository
```

Fields:

```text
id
name
path
default_branch
current_commit
primary_language
scan_status
last_scanned_at
```

---

## RepositoryFile

```text
RepositoryFile
```

Fields:

```text
id
repository_id
path
language
category
content_hash
size
```

---

## Symbol

Supported types:

```text
MODULE
CLASS
FUNCTION
METHOD
CONSTANT
ROUTE
MODEL
```

Fields:

```text
id
file_id
name
qualified_name
symbol_type
start_line
end_line
signature
docstring
```

---

## Relationship

Relationship types:

```text
DEFINES
IMPORTS
CALLS
USES
INHERITS
TESTS
EXPOSES
DEPENDS_ON
IMPLEMENTS
```

Fields:

```text
source_id
target_id
relationship_type
confidence
evidence
```

---

## Component

Higher-level engineering entity.

Possible types:

```text
controller
service
repository
client
adapter
worker
model
domain
utility
frontend_component
test_suite
```

---

## EngineeringRule

Fields:

```text
id
name
description
rule_type
status
confidence
evidence
```

Statuses:

```text
OBSERVED
PROPOSED
APPROVED
REJECTED
```

---

## ContextChunk

Used for RAG.

Fields:

```text
id
repository_id
file_id
symbol_id
chunk_type
content
embedding
metadata
commit_hash
```

---

## TraceEvent

Fields:

```text
id
task_id
repository_id
event_type
category
timestamp
metadata
```

---

# 6. Repository Ingestion

Initial implementation must support local Git repositories.

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
path exists
path is readable
path contains Git repository
repository has source files
```

The ingestion process must NEVER execute repository code.

---

# 7. Repository Scan Pipeline

Scanning must happen in stages.

## Stage 1 — File discovery

Detect:

```text
source files
tests
documentation
configuration
Docker
CI/CD
API definitions
database migrations
build files
dependency files
```

Ignore by default:

```text
.git
node_modules
.venv
venv
__pycache__
dist
build
coverage
generated binaries
```

---

# 8. Language Detection

Initially support:

```text
Python
JavaScript
TypeScript
```

Architecture must allow adding:

```text
Java
Go
C#
```

later.

---

# 9. Framework Detection

Detect frameworks using deterministic evidence first.

Examples:

```text
FastAPI
Flask
Django
React
Next.js
Express
```

Store:

```json
{
  "framework": "FastAPI",
  "confidence": 0.99,
  "evidence": [
    "fastapi found in pyproject.toml",
    "FastAPI() found in app/main.py"
  ]
}
```

Never store:

```text
framework = FastAPI
```

without evidence.

---

# 10. Symbol Extraction

For Python, use AST.

Extract:

```text
classes
functions
methods
imports
decorators
constants
function signatures
docstrings
```

Example:

```text
services/payment.py
```

produces:

```text
PaymentService
PaymentService.charge()
PaymentService.refund()
```

LLMs must NOT be used for basic symbol extraction.

---

# 11. Relationship Extraction

Create static relationships where possible.

Example:

```text
CheckoutService
CALLS
PaymentService
```

Evidence:

```text
services/checkout.py:87
```

Example relationship:

```json
{
  "source": "CheckoutService",
  "target": "PaymentService",
  "type": "CALLS",
  "confidence": 1.0,
  "evidence": {
    "file": "services/checkout.py",
    "line": 87
  }
}
```

If static analysis cannot resolve a relationship:

```text
do not invent it.
```

Use lower confidence or leave it unresolved.

---

# 12. Engineering Context Graph

Build a structured graph abstraction on top of PostgreSQL.

Do NOT require Neo4j for V0.1.

The graph should support:

```text
component → component
symbol → symbol
component → test
component → external system
component → rule
```

Example:

```text
CheckoutController
      │
      ▼
CheckoutService
      │
      ├────────► OrderRepository
      │
      └────────► PaymentService
                       │
                       ▼
                PaymentClient
```

---

# 13. Component Discovery

Group raw symbols/files into meaningful components.

Use:

1. deterministic heuristics,
2. path structure,
3. naming conventions,
4. decorators,
5. import relationships,
6. optional LLM classification.

Example:

```text
app/services/payment.py
```

may become:

```json
{
  "name": "PaymentService",
  "type": "service",
  "domain": "payments",
  "confidence": 0.96
}
```

LLM-derived classifications must retain evidence.

---

# 14. Engineering Context

Create a first-class object:

```python
class EngineeringContext:

    repository_id

    technology_stack

    frameworks

    entrypoints

    components

    relationships

    domains

    external_systems

    tests

    architecture_patterns

    engineering_rules

    uncertainties
```

This object must be persisted.

It must NOT exist only inside prompts.

---

# 15. RAG Index

Build a semantic index alongside the graph.

Index:

```text
functions
classes
methods
module summaries
README sections
architecture documents
ADRs
tests
configuration documentation
API specifications
comments where useful
```

---

# 16. Code-Aware Chunking

Do not use arbitrary fixed-size chunks for source code.

Chunk based on:

```text
class
function
method
module
test
documentation section
```

Example:

```text
PaymentClient.charge()
```

should be one coherent retrievable unit where practical.

---

# 17. RAG Metadata

Every RAG chunk must contain metadata.

Example:

```json
{
  "repository": "checkout-service",
  "path": "app/payment/client.py",
  "symbol": "PaymentClient.charge",
  "component": "payments",
  "chunk_type": "function",
  "language": "python",
  "commit": "abc123"
}
```

This metadata must allow filtered retrieval.

---

# 18. Context Engine

Implement a first-class:

```text
ContextEngine
```

Its job:

> Given a task or question, assemble the minimum trustworthy context required.

Interface:

```python
class ContextEngine:

    async def build_context(
        repository_id,
        query,
        task_type
    ) -> ContextPackage:
        ...
```

---

# 19. Retrieval Strategy

Use this priority:

```text
1 Exact symbol lookup
2 Structured metadata search
3 Graph traversal
4 Full-text retrieval
5 Vector semantic retrieval
```

Do not default every query to vector similarity.

---

# 20. Query Classification

Before retrieval, classify the query.

Possible types:

```text
STRUCTURAL
SEMANTIC
IMPACT
ARCHITECTURE
IMPLEMENTATION_LOCATION
RULE
GENERAL
```

Example:

```text
"What calls PaymentService?"
```

→ STRUCTURAL

Use graph.

---

Example:

```text
"Why does checkout behave this way?"
```

→ SEMANTIC

Use graph + RAG + docs.

---

Example:

```text
"What breaks if PaymentService changes?"
```

→ IMPACT

Use reverse graph traversal first.

---

# 21. Context Package

Retrieval must produce:

```json
{
  "query": "...",

  "facts": [],

  "graph_context": [],

  "retrieved_chunks": [],

  "rules": [],

  "uncertainties": [],

  "retrieval_trace": []
}
```

The reasoning model must receive this package.

---

# 22. Retrieval Trace

Every retrieved artifact must state why it was selected.

Example:

```json
{
  "resource": "CheckoutService",

  "reason": "reverse dependency from PaymentService",

  "retrieval_type": "GRAPH"
}
```

Example:

```json
{
  "resource": "docs/payment-architecture.md",

  "reason": "semantic similarity",

  "score": 0.87,

  "retrieval_type": "VECTOR"
}
```

This is mandatory.

---

# 23. Repository Q&A

Endpoint:

```http
POST /repositories/{id}/questions
```

Input:

```json
{
  "question": "Where is authentication implemented?"
}
```

Flow:

```text
question
↓
query classification
↓
ContextEngine
↓
structured retrieval
↓
graph retrieval
↓
RAG if needed
↓
context assembly
↓
reasoning
↓
evidence validation
↓
answer
```

Response:

```json
{
  "answer": "...",

  "confidence": "HIGH",

  "evidence": [
    {
      "file": "app/auth/service.py",
      "lines": "20-91"
    }
  ]
}
```

If evidence is insufficient:

```text
say so explicitly.
```

---

# 24. Impact Analysis

Endpoint:

```http
POST /repositories/{id}/impact-analysis
```

Input:

```json
{
  "change": "Modify the PaymentService interface"
}
```

First perform deterministic analysis.

Calculate:

```text
direct dependencies
reverse dependencies
interface consumers
tests
routes
external integrations
```

Then use LLM reasoning to explain consequences.

Example:

```json
{
  "risk": "HIGH",

  "directly_affected": [
    "CheckoutService",
    "RefundService"
  ],

  "indirectly_affected": [
    "CheckoutController",
    "RefundController"
  ],

  "tests": [
    "test_checkout",
    "test_refunds"
  ],

  "reasoning_summary": "..."
}
```

Do not ask an LLM to invent the dependency list.

---

# 25. Engineering Rule Discovery

Discover recurring repository patterns.

Examples:

```text
all HTTP clients define timeout
controllers call services
services use repositories
all public functions are typed
tests use pytest
```

Rule discovery flow:

```text
Repository Evidence
↓
Pattern Discovery
↓
Candidate Rule
↓
Confidence
↓
Human Approval
```

---

# 26. Rule Evidence

Example:

```json
{
  "rule": "HTTP clients use explicit timeout",

  "status": "PROPOSED",

  "confidence": 0.94,

  "supporting_examples": 18,

  "violations": 1
}
```

Do not automatically convert patterns into mandatory policy.

---

# 27. Repository MRI

Create a repository overview page.

Display:

```text
Repository
Technology Stack
Frameworks
Architecture
Domains
Components
Entry Points
External Systems
Tests
CI/CD
Candidate Rules
Potential Architecture Violations
```

Example:

```text
Architecture

Controller
    ↓
Service
    ↓
Repository / Client


Domains

Checkout
Payments
Customer
Orders


Observed Engineering Rules

HIGH      External HTTP clients use timeout
HIGH      Controllers use services
MEDIUM    Service layer avoids direct database access
```

---

# 28. Trace Architecture

Tracing is a core platform capability.

Implement three categories.

## Execution Trace

What happened.

Example:

```text
repository scanned
AST parser executed
graph queried
vector search executed
LLM called
```

---

## Decision Trace

Why a platform decision occurred.

Example:

```text
Graph retrieval selected because query classified as IMPACT.
```

---

## Verification Trace

Why a claim is considered supported.

Example:

```text
Framework FastAPI:
dependency evidence + FastAPI application entrypoint.
```

Do not store hidden chain-of-thought.

Store observable operational reasoning.

---

# 29. Trace Event Model

Example:

```json
{
  "task_id": "TASK-123",

  "event_type": "graph_retrieval",

  "category": "EXECUTION",

  "timestamp": "...",

  "metadata": {
    "root_symbol": "PaymentService",
    "direction": "reverse",
    "depth": 2
  }
}
```

---

# 30. Trace Store

PostgreSQL tables:

```text
tasks
trace_events
model_calls
retrieval_events
verification_results
```

Model calls must track:

```text
provider
model
tokens
latency
cost
input hash
status
```

Do not store secrets.

---

# 31. Trace Timeline UI

Example:

```text
18:31 Question received

18:31 Classified as IMPACT

18:31 Exact symbol found:
PaymentService

18:31 Reverse graph traversal:
7 dependent symbols

18:32 RAG search:
3 architecture documents selected

18:32 Context assembled

18:33 Model reasoning completed

18:33 Evidence validation passed

18:33 Answer returned
```

---

# 32. Confidence System

Every inferred claim must have confidence.

Levels:

```text
DETERMINISTIC
HIGH
MEDIUM
LOW
```

Examples:

```text
AST import
→ DETERMINISTIC

framework based on dependency + runtime entrypoint
→ HIGH

architectural pattern
→ MEDIUM/HIGH

domain interpretation based primarily on naming
→ LOW/MEDIUM
```

---

# 33. Facts vs Inference

These must be separate database concepts.

## Fact

Example:

```text
CheckoutService imports PaymentService.
```

Source:

```text
AST
```

---

## Inference

Example:

```text
Repository appears to follow layered architecture.
```

Source:

```text
pattern reasoning
```

---

## Approved Rule

Example:

```text
Controllers MUST never access repositories directly.
```

Source:

```text
human-approved engineering policy
```

Never merge these categories.

---

# 34. Incremental Scanning

Store hashes and current Git commit.

On rescanning:

```text
identify changed files
↓
remove outdated symbols/chunks
↓
reparse changed files
↓
rebuild affected relationships
↓
re-embed changed chunks
```

Do not scan the entire repository after every change.

---

# 35. Security

Repository scanning MUST:

```text
never execute repository code

never run arbitrary repository commands

never expose secrets to LLMs

detect obvious secrets before prompt creation

only send retrieved context

never send entire large repository automatically
```

---

# 36. Testing

Create fixture repositories.

At minimum:

```text
fixture_fastapi
fixture_layered_python
fixture_typescript
```

Test:

```text
file detection
symbol extraction
relationships
graph traversal
chunking
RAG metadata
retrieval classification
context construction
impact analysis
traces
confidence
```

---

# 37. Evaluation Dataset

For each fixture, define known questions.

Example:

```text
Where is the application entrypoint?

What calls PaymentService?

Which tests cover CheckoutService?

What depends on CustomerRepository?

How are external integrations implemented?
```

Expected evaluation:

```text
correct resources
correct graph relationships
correct evidence
unsupported claims
retrieval precision
answer correctness
```

---

# 38. Core Metrics

Track:

```text
retrieval precision

retrieval recall

unsupported claim rate

context size

question latency

LLM tokens

LLM cost

impact-analysis accuracy
```

These metrics must later enable adaptive optimization.

---

# 39. Future Coding-Agent Interface

Do not implement yet.

Define only:

```python
class CodingAgent:

    async def implement(
        self,
        task,
        context,
        contract
    ):
        ...
```

---

# 40. Future Task Planner

Define:

```python
class ChangePlanner:

    async def plan(
        self,
        request,
        context
    ):
        ...
```

Future output:

```text
affected components
implementation sequence
tests
risk
required context
```

---

# 41. Future Contract Layer

The future execution contract will combine:

```text
repository facts
+
approved engineering rules
+
change plan
+
task requirements
```

The contract must follow the existing principle that missing decisions must surface as blockers or assumptions rather than being silently invented.

---

# 42. Future Adaptive Layer

Do not implement yet, but traces must provide data for:

```text
failure classification
context-quality evaluation
model performance
repair strategies
model routing
engineering-rule learning
```

---

# 43. Backend Structure

Recommended:

```text
backend/

├── api/

├── repository/
│   ├── ingestion.py
│   ├── scanner.py
│   ├── inventory.py
│   └── git.py

├── parsing/
│   ├── python_ast.py
│   └── tree_sitter.py

├── graph/
│   ├── models.py
│   ├── builder.py
│   ├── traversal.py
│   └── relationships.py

├── rag/
│   ├── chunker.py
│   ├── embeddings.py
│   ├── index.py
│   └── retrieval.py

├── context/
│   ├── engine.py
│   ├── assembler.py
│   ├── classifier.py
│   └── confidence.py

├── reasoning/
│   ├── provider.py
│   ├── repository_qa.py
│   ├── impact.py
│   └── architecture.py

├── rules/
│   ├── discovery.py
│   └── approval.py

├── traces/
│   ├── events.py
│   ├── service.py
│   └── models.py

├── database/
│   ├── models.py
│   ├── session.py
│   └── migrations/

└── tests/
```

---

# 44. Required API Endpoints

```http
POST /repositories

POST /repositories/{id}/scan

GET /repositories/{id}/overview

GET /repositories/{id}/components

GET /repositories/{id}/relationships

GET /repositories/{id}/rules

POST /repositories/{id}/questions

POST /repositories/{id}/impact-analysis

POST /repositories/{id}/rules/{rule_id}/approve

POST /repositories/{id}/rules/{rule_id}/reject

GET /tasks/{task_id}/trace
```

---

# 45. MVP User Journey

```text
User connects repository

        ↓

Scan Repository

        ↓

System discovers:

technology
symbols
dependencies
components
tests
architecture
candidate rules

        ↓

System builds:

Engineering Context Graph
+
RAG index

        ↓

Repository MRI appears

        ↓

User asks:

"What depends on PaymentService?"

        ↓

Graph retrieval

        ↓

Answer + evidence

        ↓

User asks:

"Why is PaymentClient structured this way?"

        ↓

Graph
+
RAG
+
architecture docs
+
tests

        ↓

Reasoned answer + evidence

        ↓

User asks:

"What will be affected if PaymentService changes?"

        ↓

impact graph traversal
+
semantic reasoning

        ↓

risk + affected components + tests

        ↓

User opens trace

        ↓

sees exactly how context was constructed
```

---

# 46. Definition of Done

V0.1 is complete when a previously unseen repository can be supplied and the system can automatically:

```text
detect technology stack
extract symbols
build relationships
identify major components
create semantic code chunks
build graph + RAG indexes
construct repository context
answer repository questions
perform change-impact analysis
propose engineering rules
show evidence
show retrieval traces
show decision traces
distinguish facts from inference
```

No manual repository-specific configuration should be required for the basic analysis.

---

# 47. Explicit Non-Goals

Do NOT build in V0.1:

```text
autonomous coding

PR generation

deployment

multi-agent swarms

automatic repository rule enforcement

automatic rule mutation

complex enterprise RBAC

Kubernetes

microservices

custom foundation model

custom vector database

organization-wide cross-repo reasoning
```

---

# 48. First Vertical Slice

Do NOT implement the entire document simultaneously.

The first implementation milestone must be:

```text
Local Python repository
        ↓
File scan
        ↓
Python AST
        ↓
Symbols
        ↓
Imports + simple relationships
        ↓
PostgreSQL
        ↓
Code-aware chunks
        ↓
Embeddings
        ↓
Hybrid ContextEngine
        ↓
Repository Q&A
        ↓
Structured trace
```

Only after this works should the implementation continue to:

```text
components
↓
engineering graph
↓
impact analysis
↓
architecture inference
↓
rule discovery
```

---

# 49. First Demonstration

Use a small unfamiliar Python/FastAPI repository.

Demonstrate:

```text
Scan complete

Language:
Python

Framework:
FastAPI

Components:
12

Relationships:
84

Tests:
31

Candidate engineering rules:
7
```

Then ask:

> Where is authentication implemented?

Then:

> What uses CustomerService?

Then:

> What could break if CustomerService's interface changes?

Every answer must include evidence and a trace of how that evidence was retrieved.

---

# 50. North-Star Architecture

V0.1 must create the foundation for:

```text
                          REPOSITORY
                              │
                              ▼
                    ENGINEERING CONTEXT
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
            GRAPH            RAG            RULES
               │              │              │
               └──────────────┼──────────────┘
                              ▼
                       CONTEXT ENGINE
                              │
                              ▼
                      SEMANTIC REASONING
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
             Q&A           IMPACT          PLAN
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
                                                        │
                                                        └──→ CONTEXT
```

The durable product asset is not the coding model.

The durable product asset is:

```text
Engineering Context
+
Retrieval
+
Rules
+
Verification
+
Trace History
+
Adaptive Learning
```
