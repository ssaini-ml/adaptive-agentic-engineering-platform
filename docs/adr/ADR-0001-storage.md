# ADR-0001: PostgreSQL as System of Record, Optional Milvus Retrieval

- Status: Accepted
- Date: 2026-09-05
- Decision owners: Project specification and user approval

## Context

The platform needs durable repositories, immutable scans, files, symbols,
relationships, tasks, claims, corrections, and append-only traces. It will later
need dense, sparse, and hybrid retrieval over code-aware chunks.

Milvus is well suited to retrieval, but repository identity and evidence
integrity require relational constraints and transactional lifecycle management.

## Decision

Use PostgreSQL as the authoritative system of record.

Introduce a provider-neutral `RetrievalIndex` interface now. PostgreSQL
full-text retrieval is the first implementation. Milvus may be added in V0.3 only
after evaluation demonstrates improvement.

```text
PostgreSQL
├── repositories and immutable scans
├── files, symbols and relationships
├── tasks, evidence and corrections
└── authoritative trace history

Milvus, optional later
├── code-aware documents
├── dense vectors
├── BM25/sparse vectors
└── retrieval metadata referencing PostgreSQL IDs
```

Milvus records must reference repository, scan, file, symbol, and document IDs
owned by PostgreSQL. They must never become the authoritative evidence store.

## Consequences

Benefits:

- transactional scan creation and failure handling,
- relational and graph-style queries,
- database-enforced immutability,
- one authoritative source for audits,
- optional retrieval specialization without coupling the ContextEngine.

Costs:

- PostgreSQL is required for the real application,
- adding Milvus creates synchronization and operational complexity,
- a transactional outbox/index-status mechanism will be required before Milvus
  joins the critical path.

## Evaluation gate

Milvus is admitted only if it improves semantic coverage, retrieval recall, answer
correctness, or evidence support without unacceptable latency, cost, or
false-confident answers.

