# Milestone 4 — Typed Assembly and Grounded Q&A

**Status:** deterministic M4A implementation complete; model-agent activation and human release review pending

Milestone 4 turns the immutable evidence built in M1–M3C into a narrow,
auditable question-answering path. It remains read-only and language-aware. It
does not run target code, use embeddings, or authorize a coding agent.

## What is implemented

The synchronous path is:

```text
question + repository_id + scan_id
  → deterministic query contract
  → exact / graph / full-text retrieval plan
  → typed, budgeted context package
  → pre-generation coverage gate
  → deterministic structural answer renderer
  → citation / structural / lexical / qualifier validation
  → ANSWERED | PARTIAL | ABSTAINED
  → immutable answer artifacts + append-only trace
```

Supported query classes are `EXACT_SYMBOL`, `STRUCTURAL`, `LOCATION`, and
`GENERAL_STRUCTURAL`. Everything else becomes `UNSUPPORTED`. The concrete M4
intents are definition lookup, importer lookup, inheritance lookup, route
inventory, framework construction location, and bounded symbol inventory.

Canonical evidence slots include `unique_target`, `import_edges`,
`inheritance_edges`, `route_symbols`, `file_categories`,
`framework_construction`, and `containing_module`. Runtime observations,
historical rationale, call edges, and unsupported language structure are named
gaps rather than prompts for guessing.

Context slot states distinguish:

```text
FILLED
FILLED_EMPTY
AMBIGUOUS
UNFILLABLE
OMITTED_BUDGET
```

Only `FILLED` and an authoritative `FILLED_EMPTY` pass coverage. Evidence marked
partial, heuristic, ambiguous, unresolved, or generated remains labelled and
cannot silently satisfy an essential structural slot.

## Agent boundary

Two code-versioned profiles are defined:

- `repository-analyst-structural@1.0.0`
- `evidence-reviewer-structural@1.0.0`

Both are `DISABLED`. They have no direct repository access, commands, source
writes, or secret access. Their sole future entry point accepts a typed,
hash-verified handoff through a controlled model gateway. Activation requires
provider/model-specific evaluation and real human holdout review.

The current narrow structural answers are rendered deterministically, so the
implemented M4 path makes zero model calls. This is deliberate: a model agent is
not needed to restate exact structural facts, and an unsupported question must
abstain before generation. Planner, Implementer, Verifier, and Repairer roles
remain inactive.

## Persistence and traces

Migration `0006_grounded_questions` adds:

```text
question_tasks
context_packages
answers
claims
claim_evidence
```

Completed context packages, answers, claims, and evidence links are immutable at
both ORM and PostgreSQL trigger boundaries. Repeating the same canonical
question against the same scan and configuration returns the original stored
task and response, then appends `cache_hit` to its trace.

Each task trace records classification, retrieval planning/results, context
hash and omissions, coverage outcome, deterministic validation, finalization,
and cache behavior. Model interactions, when enabled later, must add provider,
model, request ID, redacted input/output hashes, token counts, latency, cost,
and outcome without storing hidden reasoning.

Human feedback is append-only. `POST /tasks/{task_id}/feedback` may link a new
`HUMAN_FEEDBACK` event to the event it corrects through `correction_of`; it never
mutates the prior answer.

## API

Ask a question:

```bash
curl -s -X POST \
  http://127.0.0.1:8000/repositories/REPOSITORY_ID/scans/SCAN_ID/questions \
  -H 'content-type: application/json' \
  -d '{"question":"Where is CustomerService defined?"}'
```

Inspect the stored result and trace:

```bash
curl -s http://127.0.0.1:8000/tasks/TASK_ID
curl -s http://127.0.0.1:8000/tasks/TASK_ID/trace
curl -s http://127.0.0.1:8000/agent-profiles
curl -s http://127.0.0.1:8000/review
```

Record a correction:

```bash
curl -s -X POST http://127.0.0.1:8000/tasks/TASK_ID/feedback \
  -H 'content-type: application/json' \
  -d '{
    "summary":"The wording needs correction.",
    "disposition":"CORRECTION_REQUESTED",
    "author_role":"HUMAN_REVIEWER",
    "corrected_event_id":"EVENT_ID"
  }'
```

The current server is local-development software and has no authentication.
Bind it only to loopback and do not expose it to an untrusted network.

## Run and verify

```bash
cd ~/Desktop/adaptive-agentic-engineering-platform
source .venv/bin/activate
docker compose up -d postgres
cp -n .env.example .env
python -m alembic upgrade head
python -m pytest
python -m ruff check backend tests
python -m adaptive_platform.qa.evaluation
python -m uvicorn adaptive_platform.main:app --app-dir backend --reload
```

Or use:

```bash
make evaluate-4
make verify
```

The M4 evaluator creates isolated temporary Git repositories from all four
language-neutral fixtures, scans them without executing their code, and checks
all 12 golden questions, including a general-structural functions-in-module
case. The current development baseline passes query-class,
slot-map, coverage, abstention, citation, false-confidence, and pre-gate model
call checks. `make evaluate-3c` remains the production PostgreSQL full-text gate;
SQLite is used only by isolated tests and the disposable M4 fixture harness.

## What remains before model-agent activation or V0.1 release

- Two engineers must independently review and adjudicate the golden labels.
- A licensed release-only holdout must be selected and evaluated.
- Each proposed provider/model configuration must pass its own answer, trace,
  cost, and adversarial-output gates.
- The minimal JSON review queue is implemented for abstentions and unresolved
  references; a polished visual console remains a release-sign-off item.
- Additional ambiguity, conflict, budget-overflow, prompt-injection, race, and
  qualifier fixtures should be expanded before release sign-off.

M4A is therefore technically complete, while M4B/M4C model-agent activation and
V0.1 human release approval remain pending.
