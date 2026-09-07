# V0.1 Outcomes

**Document version 1.5**

## Release claim

Given an unfamiliar local Git repository, the platform reports every detected
language and its analysis coverage. For Python in V0.1, it answers supported
structural questions from precise, scan-bound evidence and explicitly abstains
when evidence is insufficient. Approved text from every detected language is
available to the deterministic lexical layer even when that language's
structural adapter is not yet implemented.

V0.1 does not modify code.

## Required outcomes

### 1. Enforceable evaluation

- Three labelled Python structural fixtures, one polyglot profiling fixture, and
  one release-only holdout.
- Versioned counting rules and independent label review.
- CI reports for extraction, retrieval, evidence, answers, abstention and cost.
- No release based only on a successful demonstration.

### 2. Safe immutable scans

- Validate an explicit, allowed local Git path.
- Never import or execute repository code.
- Enforce file, byte, duration, binary, encoding and symlink limits.
- Capture commit, dirty state, content hashes and tool versions.
- Bind every artifact, question, answer and trace to one immutable scan.
- Detect and redact obvious secrets before context assembly.

### 3. Language profiling and Python evidence extraction

- Detect all repository languages using versioned, non-executing rules.
- Report primary language and `SINGLE_LANGUAGE`, `POLYGLOT`, or `UNKNOWN` type.
- Record per-language file counts, source bytes, percentages and detection signals.
- Select extractors through a language-neutral adapter registry.
- Report unsupported, partially supported and failed language coverage explicitly.
- Keep shared persistence and orchestration free of Python-specific fields.

- Extract modules, classes, functions, methods, constants, imports, decorators,
  signatures, docstrings and deterministic FastAPI routes.
- Preserve precise source spans and extractor versions.
- Keep unresolved references and their reasons.
- Distinguish evidence type from provenance.

### 4. Structural retrieval

- Case-sensitive exact symbol lookup by required name or qualified-name query.
- Structured symbol-type, file-path, language, and bounded-result filtering.
- Breadth-first, cycle-safe incoming/outgoing/both graph traversal.
- Maximum graph depth 3 and maximum 500 returned relationships.
- Deterministic result ordering and strict repository/scan isolation.
- Unresolved target, status, and reason preservation without guessed edges.
- PostgreSQL composite indexes for exact and graph access paths.
- Immutable bounded context documents for approved source, test,
  documentation, configuration, and dependency text.
- Native PostgreSQL `tsvector`, code-identifier normalization, GIN ranking, and
  a maximum of 100 cited full-text results.
- Lexical retrieval for all detected languages without misreporting structural
  adapter coverage.
- Generated, vendored, secret-flagged, changed, and unapproved text excluded
  before indexing.
- No embeddings in the V0.1 critical path.

### 5. Typed context assembly

- Query classes declare required context slots.
- Every admitted item has provenance, evidence type and trust status.
- Budgets, omissions and render strategy are logged.
- Missing essential slots trigger deterministic abstention before a model call.

### 6. Validated answers

- Claims are atomic and marked essential or optional.
- Citations resolve against the selected scan.
- Structural and lexical checks run before model-assisted entailment.
- Unsupported optional claims are removed and reported as gaps.
- Unsupported essential claims cause abstention.
- Source qualifiers are preserved.

### 7. Operational traces and review

- Repository, retrieval, decision, execution, verification and learning events.
- Reasons are recorded for selected and omitted material.
- M4A exposes task, trace, disabled-agent-profile, append-only correction, and
  JSON abstention/unresolved-reference queue endpoints; a polished visual
  console remains a release-sign-off item.
- Review effort is measured against an initial 30-minute-per-repository weekly
  operating hypothesis.

### 8. Future agent control-plane contract

- Keep the repository resource roster distinct from the worker agent roster.
- Define versioned profiles for analyst, evidence reviewer, planner, implementer,
  verifier, security reviewer, and repairer roles.
- Derive the smallest compatible task roster deterministically from the selected
  scan, language coverage, task class, risk, and required checks.
- Require typed handoffs, deny-by-default permissions, exact-file write leases,
  post-write verification, and traceable state transitions.
- Keep write-capable profiles disabled until V0.6 control-plane gates pass and
  V0.7 explicitly activates constrained coding agents.
- Catalog every system worker, control component, model agent, sandboxed runner,
  and human actor from M0 through V1.0 with implementation status.
- Keep repository evidence, orchestration workflow, and trace causality as three
  distinct graphs with typed node and edge contracts.
- Map already implemented M0–M3C nodes to their current handlers without claiming
  that a generic graph runtime exists.

## Supported V0.1 questions

```text
Where is CustomerService defined?
Which files import PaymentService?
Where is the FastAPI application created?
Which routes are defined?
Which functions exist in module X?
Which classes inherit from BaseRepository?
```

Questions requiring semantic architectural interpretation are unsupported until
V0.3 unless repository documentation directly supplies the answer.

## Milestones

| # | Status | Outcome |
|---|---|---|
| 0 | Technical foundation complete; human review pending | Evaluation harness and fixtures |
| 1 | Complete; 20 automated tests and migration check pass | Safe immutable repository scans |
| 2A | Technical implementation complete; human labels pending | Language profiling and adapter framework |
| 2B | Technical implementation complete; human labels pending | Python evidence extraction |
| 2C | Specification complete; runtime deferred | Agent roster and orchestration contracts |
| 3A | Complete; shared 3A/3B evaluator passes 18 technical gates | Scan-bound exact symbol lookup and filters |
| 3B | Complete; shared 3A/3B evaluator passes 18 technical gates | Bounded, cycle-safe evidence-graph traversal |
| 3C | Technical implementation complete; human labels pending; 22 gates pass | PostgreSQL full-text structural retrieval |
| 4A | Technical implementation complete; human labels pending | Typed assembly, deterministic grounded Q&A, cache, abstention, traces and JSON feedback surface |
| 4B/4C | Model profiles specified but disabled | Repository Analyst and Evidence Reviewer activation after provider and real holdout gates |

## Deferred

```text
V0.2  call/reference resolution, impact graph and incremental invalidation
V0.3  code-aware semantic RAG
V0.4  components, Repository MRI and candidate engineering rules
V0.5  change planning
V0.6  scan-bound execution contracts
V0.7  coding agents
V0.8  verification engine
V0.9  adaptive repair
V1.0  contract-level ratchet learning
```

Model routing is not promised at a version boundary. The trace schema accumulates
the necessary evidence, and routing begins only when sample sizes justify it.

## Demonstration

1. Scan the pinned FastAPI fixture and a labelled polyglot fixture.
2. Show detected languages, primary language, repository type, adapter coverage,
   scan and commit identity, dirty state, files, symbols, routes, imports,
   unresolved references and extractor versions.
3. Ask: **Which files import PaymentService, and which are tests?**
4. Show evidence types, exact citations and the full retrieval/assembly trace.
5. Ask a deliberately unsupported historical or architectural question.
6. Show pre-generation abstention naming the missing context slot.
7. Repeat an identical query and demonstrate byte-identical cached output.

## Success

V0.1 succeeds when its structural answers and abstentions pass the normative
evaluation gates in `EVALUATION_PROTOCOL.md`. Incremental scanning, impact
analysis and embeddings are not V0.1 acceptance requirements.
