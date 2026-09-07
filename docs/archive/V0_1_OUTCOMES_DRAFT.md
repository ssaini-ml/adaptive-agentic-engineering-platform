# V0.1 Outcomes

## Product outcome

For an unfamiliar local Python Git repository, a user can create a reproducible
scan, inspect its structure, and ask a constrained set of repository questions.
Every answer is supported by source evidence from that exact scan or clearly
states that the available evidence is insufficient.

## What we should achieve first

### 1. Trustworthy ingestion

- Accept an explicit local path.
- Verify that it is readable, is a Git worktree, and contains supported source.
- Never import or execute repository code.
- Apply explicit exclusions, file-size limits, symlink policy, and secret
  screening before model context is created.
- Record commit, dirty-state information, timestamps, and extractor versions.

### 2. Reproducible repository inventory

- Discover Python source, tests, documentation, configuration, dependency,
  migration, CI/CD, API, and build files.
- Hash file content and persist it beneath an immutable scan.
- Produce identical records from identical content and extractor versions.

### 3. Evidence graph

- Extract modules, classes, functions, methods, constants, imports, decorators,
  and FastAPI routes using Python AST.
- Store source locations and extraction provenance.
- Resolve only relationships that can be supported; retain unresolved references.
- Support forward and reverse graph traversal.

### 4. Useful questions before generative Q&A

The structured system must answer these without an LLM:

- Where is a symbol defined?
- Which files import a module or symbol?
- Which routes expose a handler?
- Which tests reference a symbol?
- What directly depends on a selected symbol?

### 5. Evidence-bound Q&A

- Route queries between exact, metadata, graph, full-text, and optional semantic
  retrieval.
- Return answer, confidence, evidence, uncertainty, scan identity, and retrieval
  trace.
- Validate citations and abstain when support is inadequate.

### 6. Measured quality

- Build three fixture repositories and golden expected outputs before optimizing
  retrieval.
- Measure extraction precision, relationship recall, retrieval precision/recall,
  unsupported claims, latency, context size, tokens, and cost.
- Admit embeddings only when they improve the benchmark rather than the demo.

## Explicitly deferred from V0.1

- JavaScript and TypeScript parsing
- Broad architecture-pattern inference
- General engineering-rule discovery
- Coding agents and source modification
- Adaptive repair and learning
- Runtime dependency tracing
- A polished multi-user frontend

These remain part of the north-star roadmap; deferral protects the correctness of
the foundation rather than removing the capabilities.

## V0.1 demonstration

1. Scan an unseen FastAPI fixture.
2. Display scan identity, commit, dirty state, inventory, symbols, routes, tests,
   and relationships.
3. Ask five golden structural questions.
4. Show answers with valid file and line evidence.
5. Ask one deliberately unanswerable question and show an explicit abstention.
6. Open the trace and reproduce why every artifact was selected.
7. Change one file, rescan, and demonstrate targeted invalidation.

## Definition of success

V0.1 succeeds when users trust its evidence enough to use the output as input to
change planning. It does not need to write code yet.
