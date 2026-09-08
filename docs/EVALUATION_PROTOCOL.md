# Evaluation Protocol

**Protocol version 1.3**

## Status

This document is normative for Adaptive Agentic Engineering Platform V0.1.
Changes require a version bump and a recorded rationale.

Version 1.3 makes the previously approximate development-fixture size targets
executable at the V0.1 release boundary and adds no new product capability claim.

## 1. Purpose

The evaluation system determines whether extraction, retrieval, assembly, and
answer validation are safe enough to release. A percentage without a counting
rule, denominator, and labelled corpus is not an acceptance gate.

## 2. Corpora

| Fixture | Target size | Purpose |
|---|---:|---|
| `fx-small` | ~40 files / ~300 symbols | exhaustive labels and fast CI |
| `fx-fastapi` | ~180 files / ~1,200 symbols | routes, DI and realistic layering |
| `fx-messy` | ~90 files | aliases, re-exports, dynamic and conditional behavior |
| `fx-holdout` | 75–250 files | release-only generalisation check |

For an enforceable V0.1 release boundary, the three Python development fixtures
must reach at least 40 (`fx-small`), 180 (`fx-fastapi`), and 90 (`fx-messy`)
inventoried files respectively. These minima make the target sizes executable;
changing them requires a protocol version bump and recorded rationale.

The repository initially contains compact seed implementations of the three
development fixtures. Expand them toward the target sizes before the V0.1 release
candidate while preserving hand-reviewable labels; fixture scale is reported in
every baseline so it cannot be hidden.

Every corpus record includes repository origin, licence, pinned commit, content
fingerprint, fixture version, label version, and counting-rule version.

Development fixtures run in CI. The holdout runs at release-candidate boundaries
and its detailed labels are not used to tune individual changes.

### Multi-language fixture matrix

The runner and normalized label schema are language-neutral. V0.1 initially
populates the Python row; every additional language must populate the same matrix
before being declared supported:

| Pack | Small | Framework/realistic | Messy | Holdout |
|---|---|---|---|---|
| Python | required | required | required | required for release |
| JavaScript | required | required | required | required for release |
| TypeScript | required | required | required | required for release |
| Java | required | required | required | required for release |
| Go | required | required | required | required for release |
| C# | required | required | required | required for release |
| Polyglot | n/a | required | required | required for release |

Fixture manifests declare `languages` and `evaluator_profile`. A polyglot fixture
declares multiple languages and labels cross-language relationships separately.
Results are reported per language, per question class, per relationship type, and
for the repository as a whole. Macro and micro aggregates are both reported; an
aggregate pass cannot override a failed supported-language gate.

Language-specific constructs remain in adapter-owned extensions while common
concepts normalize to symbols, relationships, routes/endpoints, source spans,
questions, claims, and evidence. Metrics that do not apply to a language are
reported `NOT_APPLICABLE`, never silently treated as perfect.

Every fixture also labels the language of each first-party source file, expected
primary language, repository type, generated/vendor exclusions, and expected
extractor status. Polyglot fixtures include minority-language components so a
profiler cannot pass by identifying only the dominant language.

## 3. Labelling

1. Two engineers label independently.
2. Each label references a written counting rule.
3. Disagreements are adjudicated and the rule is clarified.
4. Cohen's κ is reported where suitable.
5. For imbalanced labels, prevalence and positive/negative agreement are reported.
6. Labels are immutable within a version.

## 4. Counting rules

A symbol is counted when it is a module, class, function, method, module-level
constant, or route deterministically bound to a handler.

Nested functions count. Lambdas and comprehension variables do not. A re-export
does not create a new symbol; it creates an `EXPOSES` relationship.

An import edge is counted per `(importing_module, imported_name)`. Therefore,
`from a import b, c` produces two expected edges.

A citation is valid only when its file and complete line/column span exist in the
selected scan.

A material claim is one whose removal changes the answer to the user's question.
Question-class fixtures label essential and optional expected claims.

## 5. Question sets

Each fixture contains:

- answerable exact-symbol questions,
- answerable structural questions,
- answerable location questions,
- ambiguous questions,
- unsupported semantic or historical questions,
- adversarial questions containing misleading names,
- questions whose answer changed between scan snapshots.

Every question declares required context slots and expected answer behavior.

M4 evaluates the 12 current golden questions across `fx-small`, `fx-fastapi`,
`fx-messy`, and `fx-polyglot`. Corrected canonical slots use `unique_target`,
`route_symbols`, and `framework_construction + containing_module`; runtime and
cross-language call questions use explicit unsupported-capability slots.

## 6. Language profiling metrics

```text
language_file_precision
language_file_recall
primary_language_accuracy
repository_type_accuracy
extractor_routing_accuracy
unsupported_language_reporting_recall
```

Metrics use only independently labelled files in the denominator. Ambiguous or
unrecognized files remain explicit labels and are not silently removed. Results
are reported per language and per fixture.

Milestone 2 technical gates are:

```text
language_file_precision                 >= 0.99 on labelled known-language files
language_file_recall                    >= 0.99 on labelled known-language files
primary_language_accuracy               = 1.00 on development fixtures
repository_type_accuracy                = 1.00 on development fixtures
extractor_routing_accuracy              = 1.00
unsupported_language_reporting_recall   = 1.00
```

## 7. Extraction metrics

```text
symbol_precision
symbol_recall
import_edge_precision
import_edge_recall
route_precision
route_recall
source_span_validity
```

Call-edge resolution and precision begin in V0.2 and are not V0.1 release gates.

## 8. Retrieval metrics

```text
retrieval_precision
retrieval_recall
mean reciprocal rank
required-slot coverage
context tokens
latency p50 / p95
query classifier accuracy
context slot-map accuracy
budget/omission determinism
pre-gate model call count
```

Results are reported by question class and retrieval source. Aggregate results
must not conceal a failing question class.

## 9. Answer metrics

```text
answer_correctness
evidence_support_precision
citation_validity
claim_linkage
false_confident_answer_rate
answer_coverage
selective_accuracy
abstention_precision
abstention_recall
qualifier_preservation_accuracy
```

Definitions:

```text
false_confident_answer_rate =
  unsupported HIGH or DETERMINISTIC answers
  / all HIGH or DETERMINISTIC answers

answer_coverage =
  substantively answered answerable questions
  / all answerable questions

selective_accuracy =
  correct substantive answers
  / all substantive answers
```

Abstention precision and recall expose both unsafe answering and a system that
passes by refusing nearly everything.

## 10. Claim-validation evaluation

Maintain labelled `(claim, evidence span, verdict)` triples with verdicts:

```text
SUPPORTED
INFERENCE
UNSUPPORTED
CONFLICTING
```

Test deterministic citation, structural and lexical stages separately from
model-assisted entailment. A model must not grade itself without labelled ground
truth.

Qualifier tests include:

```text
may → must
usually → always
some → all
appears to → is
likely → certain
```

Any strengthening fails qualifier preservation.

## 11. V0.1 release gates

```text
symbol_precision            >= 0.95  fx-small and fx-fastapi
symbol_recall               >= 0.95  fx-small
import_edge_recall          >= 0.90  all development fixtures
language_file_precision     >= 0.99  labelled known-language files
language_file_recall        >= 0.99  labelled known-language files
extractor_routing_accuracy              = 1.00
unsupported_language_reporting_recall   = 1.00
full_text_case_precision                 = 1.00  six labelled M3C development cases
full_text_case_recall                    = 1.00  six labelled M3C development cases
full_text_scan_isolation                 = 1.00
full_text_safety_exclusion               = 1.00
full_text_postgresql_contract            = 1.00  tsvector, GIN, vectors, immutability
query_classifier_accuracy                = 1.00
context_slot_map_accuracy                = 1.00
coverage_decision_accuracy               = 1.00
pre_gate_model_call_count                = 0
context_budget_and_omission_determinism  = 1.00
citation_validity           = 1.00
claim_linkage               = 1.00
abstention_correctness      = 1.00  fixed unanswerable golden set
false_confident_answer_rate <= 0.02
qualifier_preservation      = 1.00  labelled qualifier set
context-cache determinism   = 1.00
holdout_regression          pass
```

Answer coverage, selective accuracy, abstention precision/recall, evidence
support precision, scan time, latency, tokens, and cost are always reported.
Their release thresholds are frozen after the first complete baseline.

The current M4 development baseline passes all 12 golden questions with 1.00
classifier accuracy, slot-map accuracy, answer coverage, abstention recall, and
citation validity; false-confident answer rate is 0 and pre-gate model calls are
0. This is not a release sign-off: fixture labels remain provisional, fixture
scale is below the target corpus sizes, the release-only holdout is unselected,
and provider-specific model gates have not run.

Before M4B/M4C model profiles can be enabled, expand the labelled suite with
case-sensitive misses, duplicate-symbol ambiguity, inheritance,
functions-in-module, authoritative empty sets, partial/unresolved edges,
misleading identifiers, prompt injection, changed snapshots, budget overflow,
conflicting evidence, invalid/out-of-scan citations, essential versus optional
claim failures, qualifier transformations, cache races, provider failures, and
malicious proposed answers.

Incremental invalidation is not a V0.1 gate. It becomes a V0.2 gate after
full-scan correctness is established.

## 12. Threshold configuration

Retrieval and trust thresholds are versioned configuration, not architectural
constants. Every deployed value records:

```text
configuration version
corpus versions
metric results
approver
approval time
rationale
```

## 13. CI and reports

Every change to scanning, parsing, retrieval, assembly, validation, or model
configuration produces a comparison report against the accepted baseline.

A release report includes:

- fixture and label versions,
- configuration and extractor versions,
- all gates,
- non-gated baselines,
- regressions by question class,
- holdout result,
- known blind spots,
- human approval.
