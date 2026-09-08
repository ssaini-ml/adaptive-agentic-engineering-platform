# Architecture Overview

This document is a map, not a source of truth. Where it summarizes a rule, the
linked normative document governs; if this page and a normative document ever
disagree, the normative document wins and this page is stale.

## The claim

> Model intelligence is rented. Engineering intelligence is accumulated.

The platform is an evidence-first control layer that builds a reproducible,
scan-bound understanding of a repository before any agent is allowed to change
it. The durable asset is not a chat transcript or a prompt — it is the
versioned evidence graph, retrieval history, approved rules, verification
history, and traces the system accumulates from its own failures. Full detail:
[SPECIFICATION.md](SPECIFICATION.md).

```text
Repository → Deterministic evidence → Versioned graph → Context assembly
           → Reasoning → Plan → Contract → Agent → Verification → Adaptation → Learning ↺
```

Everything left of "Reasoning" is built today. Everything from "Agent" onward
is specified but disabled — see [Activation state](#activation-state).

## Pipeline, as implemented

```text
1. Repository scan          immutable snapshot: commit, dirty state, content hashes
2. Language profiling       SINGLE_LANGUAGE | POLYGLOT | UNKNOWN, per-language coverage
3. Evidence extraction      Python AST → symbols, relationships, routes, unresolved refs
4. Structural retrieval     exact lookup, graph traversal, PostgreSQL full-text
5. Context assembly         typed slots, budgeted, trust-floored, coverage-gated
6. Claim validation         citation → structural → lexical → (model) entailment
7. Answer                   ANSWERED | PARTIAL | ABSTAINED, always cited, always traced
```

No step above calls a model. Stage 6's entailment check is the only stage in
the whole platform designed to use one, and it is not active in the current
build (Milestone 4A renders structural answers deterministically). Semantic
retrieval and code-writing agents are architecturally out of this pipeline
until they clear their own gates.

## Domain model (persistence)

Normative: [DATA_MODEL_AND_API.md](DATA_MODEL_AND_API.md).

| Entity | Role |
|---|---|
| `Repository` / `RepositoryScan` | mutable registration vs. one immutable, hash-bound snapshot |
| `RepositoryFile` | inventoried file with category, content hash, generated/vendored flags |
| `RepositoryLanguageProfile` | per-scan language detection and extractor coverage |
| `Symbol` / `Relationship` | the evidence graph — modules, classes, functions, routes; imports, inheritance, exposure |
| `ContextDocument` | full-text projection today; vector embeddings arrive in V0.3, not before |
| `QuestionTask` / `Answer` / claims | one question, one scan-bound answer, atomic cited claims |
| `TraceEvent` | append-only, 8 categories, every branch records its reason |

Every evidence-bearing row carries `scan_id`. Nothing is mutated after its
parent scan completes; a retry creates a new scan, never edits an old one.

## Milestone status

As of the last technical closure record
([evaluation/V0_1_TECHNICAL_CLOSURE.md](../evaluation/V0_1_TECHNICAL_CLOSURE.md)):

| Milestone | What it delivers | Status |
|---|---|---|
| 0 | Evaluation harness, fixtures, counting rules | Technical PASS; human label review pending |
| 1 | Immutable scans, commit/dirty binding | Complete |
| 2A | Language profiling, adapter registry | Technical PASS; human labels pending |
| 2B | Python AST evidence extraction | Technical PASS; human labels pending |
| 2C | Agent roster & orchestration **design** | Specification complete; nothing activated |
| 3A/3B/3C | Exact, graph, full-text retrieval | Technical PASS |
| 4A | Typed assembly, coverage gate, grounded Q&A | Technical PASS; deterministic only, zero model calls |
| 4B/4C | Model-backed agent activation | Not started |

**Every one of these is a technical pass, not a release.** V0.1 release
requires, in addition: fixture corpora expanded to their §3 target sizes, two
independent human reviewers plus adjudication
([evaluation/HUMAN_REVIEW_GUIDE.md](../evaluation/HUMAN_REVIEW_GUIDE.md)), a
licensed holdout repository evaluated at the release boundary, and a named
human approver's sign-off. `evaluation/review.json` is the source of truth for
whether that happened — see the review-process PRs alongside this document.

## Evaluation & human review

The platform will not accept its own predictions as ground truth. Every gate
is measured against fixtures with independently reviewed labels:

```text
evaluation/
├── fixtures/{fx-small,fx-fastapi,fx-messy,fx-polyglot}/   golden.json + pinned repository
├── counting-rules/v1.md                                    what counts as a symbol/import/etc.
├── HUMAN_REVIEW_GUIDE.md                                    two-reviewer independent process
├── HOLDOUT_POLICY.md                                        release-only repository, hidden from dev
└── review.json                                              real reviewer names + agreement only
```

Two engineers label independently, without seeing platform predictions or each
other's decisions, then adjudicate disagreements against the counting rules.
`false_confident_answer_rate ≤ 0.02` is the release gate that matters most —
everything upstream of it (coverage gate, claim validation, qualifier
preservation) exists to keep that number low without inflating abstention.

## Agent roster and orchestration layer

Normative: [AGENT_ROSTER_AND_ORCHESTRATION.md](AGENT_ROSTER_AND_ORCHESTRATION.md).

Two independent rosters, resolved deterministically per task:

```text
resource roster   what repository entities may be used   (projected from the evidence graph)
agent roster      which worker roles may act, in order     (projected from task class + risk + coverage)
```

Canonical roles — `REPOSITORY_ANALYST`, `EVIDENCE_REVIEWER`, `CHANGE_PLANNER`,
`IMPLEMENTER`, `VERIFIER`, `SECURITY_REVIEWER`, `REPAIRER` — are versioned
profiles, not standing personas. The design deliberately rejects a "society of
agents" in favor of the smallest compatible set per task, communicating only
through typed, hashed handoffs — never shared conversation history. A model
never approves its own irreversible action or its own release gate.

### Activation state

`backend/adaptive_platform/agents/` implements the profile/gateway scaffolding
today, but every profile ships `status: DISABLED`:

| Role | Defined | Enabled |
|---|---|---|
| `repository-analyst-structural@1.0.0` | Yes | No — requires provider evaluation + holdout review |
| `evidence-reviewer-structural@1.0.0` | Yes | No — same |
| `CHANGE_PLANNER` | Spec only | No — V0.5 |
| `IMPLEMENTER` | Spec only | No — V0.7, one constrained writer per contract |
| `VERIFIER` | Spec only | No — V0.8 |
| `REPAIRER` | Spec only | No — V0.9 |

The model gateway (`agents/gateway.py`) fails closed on a disabled profile,
schema/hash mismatch, incomplete payload, or missing gate evidence. Nothing in
the current build can write to a repository.

## What is deliberately not here yet

- **Semantic/vector retrieval.** `ContextDocument.search_vector` is full-text
  only. Embeddings enter only after an A/B against this baseline shows they
  improve accuracy/recall without unacceptable cost — see SPECIFICATION.md
  §15. The system must remain useful with embeddings disabled.
- **Any write-capable agent.** Milestone 2B's own exit condition states the
  next stage "must not activate semantic embeddings or code-writing agents."
- **A general multi-agent orchestrator.** There is no free-form
  agent-to-agent conversation anywhere in the design; see the AGENT_ROSTER
  doc's §17 design decision.
- **Model routing.** The trace schema captures what routing would need
  (model, task type, outcome, cost, latency); the router itself is out of
  scope until sample sizes justify it.

## Reading order for newcomers

1. [SPECIFICATION.md](SPECIFICATION.md) — why the platform is shaped this way
2. This document — what exists today and what's still a design
3. [DATA_MODEL_AND_API.md](DATA_MODEL_AND_API.md) — exact persistence and HTTP contracts
4. [AGENT_ROSTER_AND_ORCHESTRATION.md](AGENT_ROSTER_AND_ORCHESTRATION.md) — the agent layer's control plane
5. [evaluation/README.md](../evaluation/README.md) and
   [HUMAN_REVIEW_GUIDE.md](../evaluation/HUMAN_REVIEW_GUIDE.md) — how any of the above gets trusted
