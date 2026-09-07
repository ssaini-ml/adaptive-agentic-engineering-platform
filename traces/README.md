# Traces

The platform records observable operational decisions, model interactions, human
corrections, verification results, and learning signals.

It never stores hidden model chain-of-thought.

## Required trace behavior

A model decision records:

```text
provider and model
request ID when available
prompt-template and configuration versions
redacted input and output hashes
selected evidence references
decision summary
observable rationale summary
tool calls
tokens, latency and cost
validation outcome
```

A human correction records:

```text
author identity or role
channel
target event through correction_of
redacted correction summary
accepted / rejected / partially accepted
artifacts changed
follow-up verification
```

The correction event and resulting decision share a correlation ID. This supports
the audit sequence:

```text
model decision
      ↓
human correction
      ↓
revised decision
      ↓
artifact change
      ↓
verification
      ↓
learning signal
```

## Development storage

Milestone 0 uses JSON Lines. Each line is one event conforming to
`trace-event.schema.json`.

`design-history.jsonl` records observable decisions and corrections from the
initial specification work. It is not hidden reasoning and should not contain
secrets or full prompts.

Milestone 1 moves authoritative runtime traces to PostgreSQL while retaining JSONL
export for debugging and audits.

Milestone 3 runtime retrieval events are:

```text
exact_symbol_retrieval_completed
graph_traversal_completed
context_documents_created
full_text_retrieval_completed
```

Retrieval events bind to the repository and immutable scan. Query-bearing events
store SHA-256 rather than raw query text, plus bounded filters, result counts,
engine identity, and returned evidence references. The context-document event
records admission/exclusion counts and search configuration. These deterministic
system events are not mislabelled as LLM decisions; future model-backed M4
analysis will use `MODEL_INTERACTION` and `DECISION` events with evidence links.

Milestone 4 question tasks use one task/correlation ID across:

```text
question_received
task_classified
cache_miss | cache_hit
retrieval_planned
exact_retrieval_completed | graph_retrieval_completed | full_text_retrieval_completed
context_assembled
coverage_passed | coverage_failed
claims_validated
question_answered | question_partial | question_abstained | question_failed
human_correction_recorded
```

Coverage events record the model-call count, which must be zero for unsupported
or under-covered tasks. `human_correction_recorded` may point to the corrected
event through `correction_of` and never mutates the stored answer. The two M4
model profiles are currently disabled; when one is enabled, its gateway call
must add a `MODEL_INTERACTION` event with the metadata listed above.

## Retention and redaction

Raw prompts and responses are disabled by default. Prefer hashes and references to
scan-bound evidence. If raw content retention is explicitly enabled later, it
requires secret redaction, an approved retention period, access control, and
deletion support.
