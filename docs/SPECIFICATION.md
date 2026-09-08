# Adaptive Agentic Engineering Platform

**Specification v3.5** · implemented deterministic grounding boundary

This is the canonical product and architecture specification. Its normative
companions are:

- `EVALUATION_PROTOCOL.md` — fixtures, labels, metrics and release gates.
- `DATA_MODEL_AND_API.md` — persistence entities, constraints, APIs and errors.
- `V0_1_OUTCOMES.md` — concise delivery contract for the current release.
- `AGENT_ROSTER_AND_ORCHESTRATION.md` — future agent roles, permissions,
  selection, handoffs, lifecycle and activation gates.

---

## What changed in v2 through v3.5

| # | Issue in v1 | Resolution |
|---|---|---|
| 1 | Acceptance gates stated as bare percentages with no denominator or labelling protocol | §3 defines fixture size, labelling procedure, unit-of-count rules, and agreement bar. Gates are now falsifiable. |
| 2 | `CALLS` treated as adjacent in difficulty to `IMPORTS` | §7 sets a separate resolution-rate target for call edges and defines what happens to the unresolved remainder |
| 3 | "Evidence supports the claim" — one line for the hardest component | §11 specifies claim validation as a staged pipeline with its own eval |
| 4 | Flagship demo question is semantic; V0.1 has no semantic retrieval | §14 replaces it with a structural question and states the limit plainly |
| 5 | Determinism gate incompatible with a model in the loop | §12 derives determinism from context-hash caching, not from model behaviour |
| 6 | Human approval required in three places, no interface until "later" | §13 pulls a minimal review console into V0.1 and budgets the human minutes |
| 7 | Model routing promised at V1.0 on data volumes that will not exist | §19 keeps the trace schema, drops the router from the roadmap |
| 8 | Contracts not bound to a scan | §16 binds every contract to `scan_id` and rejects execution against a moved tree |
| 9 | Language packs existed, but repository-language detection and adapter coverage were implicit | §2 makes scan-bound language profiling, polyglot classification, adapter routing and unsupported-language reporting normative |
| 10 | The contract's repository resource roster did not define worker roles or orchestration | §16 separates resource and agent rosters; the companion agent-roster specification defines deterministic selection, permissions, typed handoffs, lifecycle, concurrency and activation gates |
| 11 | The agent roster listed future model roles without mapping existing deterministic workers or graph nodes | The companion specification now catalogs every M0–V1.0 actor, separates evidence/orchestration/trace graphs, defines node and edge contracts, and maps implemented nodes to code |
| 12 | Structural retrieval was one undifferentiated milestone without query, traversal, ordering, or resource limits | §7.1 separates M3A exact lookup, M3B bounded graph traversal, and M3C full-text retrieval; all three contracts are now implemented and independently testable |
| 13 | Full-text retrieval was named without an admission policy, chunk bound, code-token strategy, database contract, filters, traces, or polyglot gate | §7.1 and the M3C implementation guide define immutable context documents, conservative exclusions, 200-line/20,000-character chunks, code-aware `simple` vectors, native PostgreSQL ranking, typed citations, limits, runtime traces, and a 22-gate evaluator |
| 14 | Route queries were specified as graph-edge slots even though routes are recorded symbols | v3.5 makes `route_symbols` canonical and evaluates it against the FastAPI fixture |
| 15 | Framework location required a nonexistent exact `app` symbol | v3.5 requires `framework_construction` plus `containing_module` and validates the construction syntax in bounded source |
| 16 | Model-agent names could be mistaken for active agents | v3.5 implements read-only profile and typed-handoff contracts but keeps Repository Analyst and Evidence Reviewer `DISABLED` until provider gates and real human holdout review pass |
| 17 | Missing, empty, ambiguous, and budget-omitted context were conflated | v3.5 freezes `FILLED`, `FILLED_EMPTY`, `AMBIGUOUS`, `UNFILLABLE`, and `OMITTED_BUDGET`; only the first two pass coverage |
| — | Context assembly implicit and untyped | §9 makes it a first-class stage with budget, typing, trust floors and degradation policy |
| — | Accumulation starts only at V1.0 | §18 begins accumulating at V0.1 from abstentions and unresolved references |
| — | Incremental scanning was required without appearing in the V0.1 milestones | Full-scan correctness remains in V0.1; incremental invalidation moves to V0.2 |
| — | All abstentions were excluded from caching | Deterministic coverage abstentions are cacheable; failures are not |
| — | One unsupported claim forced total abstention | Optional unsupported claims are removed; essential unsupported claims cause abstention |
| — | Provenance and evidence type could be confused | They are separate, orthogonal dimensions |
| — | Repeated fixtures risked benchmark overfitting | A release-only holdout repository is required |

---

# Part I · Position

## 1. The claim

The platform is an engineering control layer that understands a repository before any agent modifies it.

Not:

```
Repository → Vector DB → LLM
```

But:

```
Repository → Deterministic evidence → Versioned graph → Context assembly
           → Reasoning → Plan → Contract → Agent → Verification → Adaptation → Learning ↺
```

The durable asset is versioned engineering context: the evidence graph, retrieval history, approved
rules, verification history, execution traces, and everything the system has learned from its own
failures. Foundation models are replaceable workers against that asset.

> **Model intelligence is rented. Engineering intelligence is accumulated.**

The strategic risk in v1 was that accumulation began at V1.0, nine milestones out. §18 fixes that.

## 2. What V0.1 must prove

One claim, exceptionally well:

> Given an unfamiliar local Git repository, the platform profiles every detected language and, for
> Python in V0.1, answers supported **structural** questions from precise, scan-bound evidence while
> abstaining explicitly when its evidence is insufficient.

V0.1 does not write code. *Can we understand the repo reliably* must be answered before *can an agent
safely change it.*

### Language scope versus evaluation architecture

V0.1 proves the product with Python, but the evaluation system itself is
language-neutral. Fixture manifests declare one or more languages and an
evaluator profile; the runner discovers manifests rather than hardcoding Python
fixtures.

Language support ships as independently gated language packs:

```text
Python                 first V0.1 pack
JavaScript/TypeScript  next language pack
Java, Go, C#           later language packs
POLYGLOT               cross-language relationship pack
```

Every pack needs its own counting rules, small/framework/messy fixtures, golden
labels, unsupported questions, and holdout evaluation. Passing Python gates must
never conceal a failing TypeScript or mixed-language pack.

### Repository language profiling

Language profiling runs for every completed scan before evidence extraction. It
detects all languages rather than asking the user to select one. Detection uses
versioned rules over extensions, well-known filenames, shebangs, repository and
workspace markers, and generated/vendor classifications. It never imports,
builds, or executes repository code.

The profile stores, per language, first-party source-file count, first-party
source bytes, byte percentage, generated-file count, detection signals, and
extractor coverage. Generated, vendored, documentation, configuration, and
dependency artifacts are reported separately and do not determine the primary
language.

```text
repository_type   SINGLE_LANGUAGE | POLYGLOT | UNKNOWN
extractor_status  SUPPORTED | PARTIAL | UNSUPPORTED | FAILED
```

The primary language is the language with the most first-party source bytes. A
profile is `POLYGLOT` when two or more languages each contribute at least 5% of
first-party source bytes, or when versioned workspace/module markers establish
components in different languages. It is `UNKNOWN` when no language can be
identified. Classification thresholds are configuration-versioned.

Detection and support are different facts. A detected language without an
approved adapter remains visible as `UNSUPPORTED`; it is never discarded or
misrepresented as successfully analysed. Polyglot scans may run several adapters
and must report evidence coverage and failure independently for each language.

### Extractor adapter contract

Every language pack implements the same adapter boundary: declare supported
language identifiers and adapter version, accept only scan-bound files, and emit
normalized symbols, relationships, routes, source spans, unresolved references,
and diagnostics. Language-specific constructs live in adapter-owned extension
metadata and cannot introduce language-specific columns into the shared core
model. The registry selects adapters from the stored language profile; Python is
the first implementation, not a special case in orchestration or persistence.

---

# Part II · Making the gates enforceable

## 3. Evaluation protocol

Milestone 0, before any product feature. A threshold without a denominator and a labelling procedure
is not a gate — it is an aspiration that gets waved through at review.

### Fixtures

Three development repositories, fixed at a commit and vendored into the test
suite, plus one separately maintained holdout repository:

| Fixture | Size | Purpose |
|---|---|---|
| `fx-small` | ~40 files, ~300 symbols | fast CI, exhaustive hand labels |
| `fx-fastapi` | ~180 files, ~1,200 symbols | routes, DI, realistic layering |
| `fx-messy` | ~90 files | dynamic imports, decorators, re-exports, conditional imports |
| `fx-holdout` | 75–250 files | release-only generalisation check; hidden from feature development |

`fx-messy` exists so the resolution ceiling is measured rather than assumed.
`fx-holdout` is evaluated at release-candidate boundaries, has a documented
licence, and is pinned to a commit.

### Labelling procedure

1. Two engineers label independently against a written counting rule.
2. Disagreements are resolved in review; the resolution is appended to the counting rule.
3. Cohen's κ ≥ 0.85 on the first pass where κ is statistically appropriate. For
   highly imbalanced labels, report prevalence plus positive and negative
   agreement. Ambiguous counting rules are rewritten.
4. Labels are versioned with the fixture commit and the counting-rule version.

### Counting rules (excerpt — the full document lives with the fixtures)

A **symbol** is counted when it is a module, class, function, method, module-level constant, or a
route deterministically bound to a handler. Nested functions **are** counted. Re-exports through
`__init__.py` are **not** counted as new symbols; they create an `EXPOSES` edge to the original.
Comprehension variables, lambdas and `TYPE_CHECKING`-only imports are **not** counted.

An **import edge** is counted per `(importing_module, imported_name)` pair, not per statement.
`from a import b, c` is two edges.

### Metrics, separately reported

```
symbol_precision              symbol_recall
import_edge_precision         import_edge_recall
call_edge_resolution_rate     call_edge_precision
retrieval_precision           retrieval_recall
evidence_support_precision    ← distinct from retrieval precision, see §11
answer_correctness            abstention_correctness
false_confident_answer_rate   selective_accuracy
answer_coverage               abstention_precision / abstention_recall
context_tokens                latency_p50 / p95        cost_per_query
```

`evidence_support_precision` is the one most teams never measure. Retrieving `checkout.py` for a claim
about authentication is precise retrieval and zero support.

---

## 4. Evidence taxonomy and provenance

Six types, never collapsed to a deterministic/inferred binary. Each carries a **trust class** that
drives assembly (§9).

| Type | Example | Trust class |
|---|---|---|
| `SYNTAX_FACT` | `from payments import PaymentService` appears at line 3 | authoritative |
| `STATICALLY_RESOLVED` | `CheckoutService` calls `PaymentService.charge` | authoritative |
| `HEURISTIC` | `payment.py` looks like a service component | corroborated |
| `SEMANTIC_INFERENCE` | the repo appears to follow layered architecture | unverified |
| `HUMAN_APPROVED_RULE` | controllers must not touch repositories | authoritative |
| `RUNTIME_OBSERVATION` | trace X shows `StripeAdapter` was called | authoritative, scoped to that trace |

Static truth and runtime truth are never silently equated. A syntax fact proves a name is imported;
it does not prove which object executes.

Evidence type answers **what kind of claim this is**. Provenance independently
answers **where its representation came from**:

| Provenance | Meaning |
|---|---|
| `RECORDED` | copied from an addressable source span or approved record |
| `DERIVED` | computed reproducibly from recorded inputs |
| `GENERATED` | produced by a model and not independently established |

Examples include `RECORDED + SYNTAX_FACT`, `DERIVED + STATICALLY_RESOLVED`, and
`GENERATED + SEMANTIC_INFERENCE`. Anything derived from generated material keeps
generated taint unless independently verified against recorded evidence.

---

## 5. Immutable scans

`RepositoryScan` is a first-class object. Every evidence-bearing artifact belongs to
`(repository_id, scan_id, commit_hash, extractor_version)`.

For dirty trees, a commit hash is insufficient. Either capture per-file content hashes, or reject the
scan. This prevents *graph from commit A + source from commit B* reaching one answer — the failure
that makes a system quietly untrustworthy rather than loudly broken.

**Extended in v2:** the binding is not only for scans. Every contract, plan and verification run
carries `scan_id`, and execution is rejected if the tree has moved (§16).

---

## 6. Domain model

The complete normative model and API definitions live in
`DATA_MODEL_AND_API.md`. `Relationship` retains `resolution_status ∈ {RESOLVED,
PARTIALLY_RESOLVED, HEURISTIC, UNRESOLVED}`. Its `target_id` is nullable when
resolution fails, while `unresolved_target` and `resolution_reason` preserve what
could not be established. Source spans use structured file, line and column
coordinates rather than an opaque location string.

---

## 7. Static resolution: the honest ceiling

v1 treated `IMPORTS` and `CALLS` as adjacent milestones. They are an order of magnitude apart.

`IMPORTS` is tractable with the `ast` module. `CALLS` runs into dynamic imports, `__getattr__`,
decorators that rewrite functions, DI containers, `importlib`, re-exports, monkeypatching in tests, and
conditional imports under `TYPE_CHECKING`. Without type inference, expect **60–80% resolution on real
code** — and the unresolved remainder is not random. It clusters on exactly the framework magic that
matters most.

### Policy

- **V0.2 target:** ≥ 90% call-edge resolution on `fx-small`, ≥ 75% on `fx-messy`.
- Missing the `fx-messy` target is a signal to add type inference, **not** to ship a graph with silent
  holes.
- Every unresolved call is persisted with the reason (`dynamic_dispatch`, `unresolved_import`,
  `decorator_rewrite`, …).
- Any answer whose traversal crossed an unresolved edge **must** say so. A dependency list that
  silently omits what could not be resolved is worse than no list, because it looks complete.

## 7.1 Structural retrieval

Structural retrieval is a deterministic projection of one immutable evidence
graph. It is language-neutral: adapters populate normalized `Symbol`,
`Relationship`, and source-span records, and the retrieval core does not branch
on Python syntax.

Milestone 3 is split into independently verifiable parts:

| Part | Status | Contract |
|---|---|---|
| M3A | Implemented | case-sensitive exact `name` or `qualified_name` lookup, with scan-bound symbol type, file-path, language, and result-limit filters |
| M3B | Implemented | cycle-safe `INCOMING`, `OUTGOING`, or `BOTH` traversal with relationship filters, maximum depth 3, maximum 500 returned edges, and stable ordering |
| M3C | Implemented | bounded PostgreSQL full-text retrieval over immutable approved documents, with code-identifier normalization, typed citations, filters, GIN indexing and polyglot gates |

Exact lookup does not silently broaden to prefix, fuzzy, case-insensitive, or
semantic matching. Graph traversal never crosses a repository or scan boundary.
Resolved targets may be expanded once at their shallowest breadth-first depth;
unresolved targets are returned with their original text and reason but cannot
be traversed. Stable sort keys and UUID tie-breakers make pagination prefixes and
repeated calls reproducible.

Composite database indexes serve exact-name, qualified-name, file-filter,
outgoing-edge, and incoming-edge access paths. They are optimizations over the
PostgreSQL source of truth, not a separately authoritative graph store. The
normative request and response behavior is defined in `DATA_MODEL_AND_API.md`;
the operational guides are `MILESTONE_3.md` and `MILESTONE_3C.md`.

M3C creates immutable `ContextDocument` records while a scan is still running,
then populates native PostgreSQL `tsvector` values and seals the scan. Approved
source, test, documentation, configuration, and dependency files are chunked to
at most 200 lines and 20,000 characters. Generated, vendored, secret-flagged,
unsafe, changed, and unapproved material is excluded explicitly. PostgreSQL uses
the `simple` configuration plus derived dotted, snake-case, path-like, and
camel-case identifier terms. Search is limited to 100 hits and a 256-character
query, remains repository/scan bound, and always returns file/line citations.
Lexical indexing covers detected languages without requiring a structural
adapter. SQLite's deterministic fallback exists only for tests and does not
satisfy the PostgreSQL M3C gate.

---

# Part III · Context engineering

This part is new in v2. v1 treated context as something the retrieval layer produced and the reasoner
consumed. Making the assembly stage explicit and typed is what turns retrieval quality into answer
quality.

## 8. The governing principle

> **An empty slot is a decision the model will make for you — silently, and differently each time.**

Applied to a repository system: anything the context package does not carry, the reasoner will supply
from its priors. It cannot distinguish *"not in the context"* from *"does not exist in the
repository."* Both look identical from inside the window.

That single fact drives §9 through §12.

## 9. Context assembly as a first-class stage

Retrieval returns candidates. **Assembly** decides what actually enters the window, in what order,
under what budget, with what labels. v1 had no such stage; the `ContextPackage` was an untyped bag.

```python
class ContextPackage(BaseModel):
    query: str
    scan_id: UUID
    slots: list[ContextSlot]        # typed, ordered, budgeted
    unfillable: list[str]           # declared but not satisfiable — see §10
    assembly_log: list[AssemblyEvent]
    context_hash: str               # drives determinism, see §12
```

### Typed slots

Every item carries a status that **propagates**: anything derived from generated content is itself
generated.

| Status | Meaning | Rendered as |
|---|---|---|
| `RECORDED` | traceable to a source span in this scan | quoted with `path:line` |
| `DERIVED` | computed from recorded material | labelled with its inputs |
| `GENERATED` | produced by a model, no source | labelled explicitly, never presented as record |

Once "the code does X" and "a model inferred X" occupy the same field in the same format, nothing
downstream can tell them apart, and the final answer presents both as fact.

### Budget and fill order

Slots compete for the window under a declared fill order, not a concatenation order:

1. Task frame and abstention rules — never truncated; if these do not fit, the query is misconfigured
2. Approved rules for this repository
3. Exact-match evidence
4. Graph context
5. Full-text results, in trust order
6. Optional background, best effort

A verbose retrieved file can now only consume its own slot's allocation. It cannot push the task
specification into the middle of the window where attention is weakest.

**Position is a resource, not just size.** Render order need not match fill order.
Strategies such as `TASK_FIRST`, `TASK_BOOKENDED`, `EVIDENCE_FIRST`, and
`PROVIDER_OPTIMIZED` are versioned configuration, not universal truth. Select a
strategy through evaluation and record it in the assembly log.

### Trust floors by evidence type

Retrieval scores are not comparable across sources, so floors are per-class:

| Source class | Floor | Below floor |
|---|---|---|
| Exact symbol match | n/a — exact or absent | — |
| Graph edge, `RESOLVED` | admit | — |
| Graph edge, `PARTIALLY_RESOLVED` | admit **labelled** for recorded syntax only | cannot establish runtime behavior or completeness |
| Graph edge, `HEURISTIC` | admit **labelled** | — |
| Graph edge, `AMBIGUOUS` or `UNRESOLVED` | admit **labelled** | cannot fill an essential structural slot |
| Full-text | evaluated configuration | omit or admit labelled, logged |
| Approved rule | admit | — |
| Semantic (V0.3+) | evaluated configuration | quarantine, logged |

Numeric floors are not architectural constants: distributions differ by index,
corpus and provider. Every deployed threshold carries a configuration version and
evaluation result. Semantic retrieval normally requires stricter admission because
weak semantic hits can appear convincingly relevant.

### Degradation policy

Three options exist, and the middle one is the one people forget:

- `omit` silently → an answer that is **confidently ignorant**
- `admit` silently → an answer that is **confidently wrong**
- `admit_labeled` → an answer that is **appropriately uncertain** ← default

Nothing is ever dropped silently. Every omission is an `AssemblyEvent` with a cause.

### "Noise" is consumer-specific

Do not build one canonical cleaned representation that every consumer reads. A Q&A query and an impact
analysis need different projections of the same scan, and a shared preprocessing step can only serve
consumers that agree on what noise is. Where two consumers disagree, give them different views — or
give them the source and let each filter.

## 10. The coverage gate

Before generation, assembly asks one question: **can the retrieved evidence fill every slot this
question requires?**

```
question class → required slots → can they be filled?
                                    │
                            no ─────┴───── yes
                             │              │
                        abstain,        render or invoke an enabled analyst
                     naming the gap
```

If not, abstain **before** the model call and name the missing slot. Do not let the reasoner fill it.
This is the cheapest gate in the system and it runs before any token is spent.

The implemented M4 contract uses intent-specific slots rather than generic
retrieval buckets: definition requires `unique_target`; importer/inheritor
queries require `unique_target` plus the corresponding incoming edges; routes
require `route_symbols`; framework location requires
`framework_construction + containing_module`. `FILLED_EMPTY` is valid only for
an authoritative set-valued lookup, never for a unique target.

## 11. Claim validation

v1 gave this one line. It is the hardest component in the platform and it decides whether the product
answers or abstains — so its failure mode *is* the product's failure mode.

### Staged pipeline, cheapest first

```
answer draft
  ↓ 1  claim extraction        split into atomic, individually checkable claims
  ↓ 2  citation resolution     does path:line exist IN THIS SCAN?          [deterministic]
  ↓ 3  span retrieval          pull the actual source text
  ↓ 4  structural check        does the graph contain the asserted edge?    [deterministic]
  ↓ 5  lexical check           do the claim's entities appear in the span?  [deterministic]
  ↓ 6  entailment check        does the span support the claim?             [model, last resort]
  ↓ 7  verdict                 SUPPORTED | INFERENCE | UNSUPPORTED
```

Stages 2, 4 and 5 are deterministic and catch the majority of failures at near-zero cost. Stage 6 runs
only on what survives, and its own error rate is measured separately against a labelled set of
(claim, span, verdict) triples — otherwise §3's `evidence_support_precision` is one model grading
another with no ground truth.

### Rules

- An unsupported optional claim is removed and reported as a gap. An unsupported
  essential claim demotes the answer to abstention. Question-class definitions
  declare which claims are essential.
- `INFERENCE` is allowed but must be labelled inline, not in a footer.
- Conflicting evidence is surfaced, never silently resolved by preferring one source.
- **Hedges are preserved.** If the source says "usually" or "in most cases", the answer may not say
  "always". Qualifiers are the first thing compression drops and the last thing a reader notices is
  missing.

### Qualifier preservation as a metric

Measure semantic preservation of qualifiers against labelled transformations.
Changes such as `may → must`, `usually → always`, `some → all`, or `appears to →
is` fail validation. Raw hedge density is only a diagnostic because it can be
gamed by adding meaningless qualifiers.

## 12. Determinism without a deterministic model

v1's gate — *deterministic structured output for identical inputs* — cannot be met by calling a model.
`temperature=0` is not a guarantee across provider versions.

Determinism comes from **not calling the model**:

```
question + scan_id + extractor_version
        ↓ canonicalise           normalise whitespace, sort slots, drop volatile fields
        ↓ context_hash           sha256
        ↓ cache lookup
   hit → return original stored task and answer  ← byte-identical response, no model call
  miss → generate, validate, store on success only
```

A deterministic coverage-gate abstention is cacheable because its missing slots
are reproducible for the same scan and configuration. Validation failures, model
failures and transient provider failures are never cached.

The cache key includes the canonical question, scan ID, content fingerprint,
extractor versions, classifier version, retrieval configuration, assembler
version, validator version, and model configuration where a model was used.

Revised gate: *identical inputs and extractor versions produce byte-identical output via the context
cache, and a cache miss produces an answer that passes claim validation.*

---

# Part IV · Product

## 13. Human review, budgeted and staffed

Rule approval, contract review and ratchet approval all need a human. v1 deferred the frontend, which
means these run through SQL or not at all. This is what kills systems in this class — not the ML, the
approval queue nobody staffs.

**V0.1 requires a minimal review surface.** M4A exposes JSON task, trace, agent
profile, append-only feedback, abstention-queue, and unresolved-reference-queue
endpoints plus a small local visual projection of the two queues. The page can
append task feedback without mutating prior answers:

```
Abstentions        questions the system could not answer, and why
Unresolved         references the extractor could not resolve
Candidate rules    (V0.4+) observations awaiting approval
```

Initial operating hypothesis: **up to 30 minutes per repository per week** at
steady state. Measure this during pilots; it is a product budget to validate, not
a universal constant. Repeated excess means the thresholds or workflow must
change.

Review the **contract**, not the diff. Nine slots take thirty seconds and catch the expensive errors
before code exists. Reviewing generated code is slow and gets rubber-stamped.

## 14. V0.1 scope and the demo

Supported question classes: `EXACT_SYMBOL`, `STRUCTURAL`, `LOCATION`, `GENERAL_STRUCTURAL`,
`UNSUPPORTED`.

```
Where is CustomerService defined?
Which files import PaymentService?
Where is the FastAPI application created?
Which routes are defined?
Which classes inherit from BaseRepository?
```

**Demo question changed.** v1's flagship — *"Where is authentication implemented?"* — is semantic, and
V0.1 has no semantic retrieval. Full-text on "auth" works when the codebase happens to use that word
and fails on the repositories where help is most needed. Promising it sets up a demo the architecture
cannot deliver.

V0.1 demo question:

> **Which files import `PaymentService`, and which of them are tests?**

Deterministic, verifiable against the graph, and it shows citations, evidence typing and the trace.
Keep *"Where is authentication implemented?"* as the V0.3 demo, where it belongs.

## 15. Retrieval sequence

```
1. exact symbol lookup
2. structured metadata
3. graph traversal
4. PostgreSQL full-text
—— V0.3, only if it earns its place ——
5. semantic retrieval
```

Vector retrieval enters the critical path only after A/B against the baseline shows it improves answer
accuracy, evidence recall or semantic coverage without unacceptable cost in latency, spend or
unsupported-claim rate. **The system must remain useful with embeddings disabled.**

## 16. Contracts bound to scans

When execution arrives (V0.6+), the contract carries the same binding as everything else:

```yaml
contract:
  id: RETRY-001
  version: 1.0.0
  scan_id: <uuid>          # the evidence this contract was written against
  commit_hash: <sha>
  content_hashes: {...}    # for dirty trees

  goal: ...
  slots: {who, what, to_what, comes_back, when, when_not, how, on_exhaust, force}
  constraints: {purity, concurrency, latency_budget, observability, security}
  resource_roster: ...     # allowed repository entities; see below
  agent_roster_ref: ...    # selected worker roles and permissions
  forbidden: [...]
  checks: [...]            # each names the slot it defends
```

Execution is **rejected** if the working tree has moved since `scan_id`. Without this, the exact bug
the snapshot design prevents at analysis time reappears at execution time.

### The resource roster is derivable from the scan

This is the strongest integration between the two halves of the platform. The closed world does not
have to be hand-written — it is a projection of the evidence graph:

```
resource_roster.modules    ← imports resolved in this scan + declared dependencies
resource_roster.symbols    ← symbols reachable from the change site
resource_roster.exceptions ← exception types already defined or imported
forbidden                  ← any dependency not in pyproject.toml
```

A model reaching for `Redis` in a repository that has never imported it is **invention, not
inference** — and the scan already knows that. Enforcement is a twenty-line AST walk over the
generated patch.

### The agent roster is derived from the task

The resource roster answers **what may be used**. The agent roster answers **who
may act, in which order, with what authority**. These are independent contracts;
selecting an agent never expands the resource roster.

The canonical future roles are `REPOSITORY_ANALYST`, `EVIDENCE_REVIEWER`,
`CHANGE_PLANNER`, `IMPLEMENTER`, `VERIFIER`, `SECURITY_REVIEWER`, and `REPAIRER`.
The deterministic orchestrator selects the smallest compatible subset from the
task class, scan language coverage, change scope, risk policy and required checks.
Identical inputs and configuration must produce the same roster.

Read-only roles may operate concurrently against one scan. The default execution
topology permits one writer, requires a write lease over exact files, and requires
verification after every write. Unsupported language coverage blocks a writer
for that language. Roles exchange typed, hashed handoff artifacts rather than
free-form conversation history.

The normative profile schema, roster schema, permission matrix, state machine,
failure routing, evaluation gates and phased activation are defined in
`AGENT_ROSTER_AND_ORCHESTRATION.md`. Agent profiles remain disabled until their
roadmap predecessor and gates pass.

That companion also contains the complete lifecycle actor roster from M0 through
V1.0 and three non-interchangeable graph contracts: the repository evidence
graph, orchestration workflow graph, and append-only trace causality graph. Each
orchestration node has a typed input/output contract, guards, permissions,
idempotency key, status and handler reference; each edge has a stable condition,
handoff schema and failure transition.

## 17. Adaptive repair

Never `try again`. Resampling without new information burns budget without converging.

Classify first:

```
SPECIFICATION_GAP · IMPLEMENTATION_ERROR · CONTEXT_MISSING · ARCHITECTURE_VIOLATION
SECURITY_VIOLATION · DEPENDENCY_VIOLATION · TEST_FAILURE · MODEL_LIMITATION
CONFLICTING_REQUIREMENTS
```

Then escalate one rung at a time. Each rung costs more and constrains more, so climb only as far as
the failure requires:

| Rung | Strategy | Use when |
|---|---|---|
| 1 | restate | first failure, may be sampling noise |
| 2 | name the failing slot | the failure is specific |
| 3 | counterexample | the model does not see why it is wrong |
| 4 | expand context | classified `CONTEXT_MISSING` |
| 5 | switch model | same slot failed twice on the same model |
| 6 | human escalation | budget exhausted |

If no alternative model is configured, say so in the trace and escalate. Do not silently loop.

Every rung records: strategy, **why it was selected**, evidence used, and prior failures. "Switched
model" is useless; "switched model because `when_not` failed twice on model-a" is diagnosable.

## 18. The ratchet — starting at V0.1

v1 introduced learning at V1.0. That is nine milestones before the product starts compounding, which
is too late to validate the central strategic claim.

**V0.1 already produces two learning signals, for free:**

```
every abstention          → a question class the evidence cannot support
every unresolved edge     → a resolution capability that is missing
```

Log both from day one, cluster them weekly, and the backlog writes itself from real gaps rather than
from guesses. The review console (§13) surfaces exactly these two queues.

From V0.6 the same loop runs on contracts:

```
collect assumptions and failed slots
  → ask: which slot should have made this unnecessary?
  → add the slot, bump the minor version
  → add a check that defends it     (a slot with no check is a wish)
  → promote to the team template if it generalises
```

Most output-quality complaints are specification complaints in disguise:

| observed | the slot never filled |
|---|---|
| doesn't handle empty input | no `when` for that case |
| it's O(n²) | no complexity constraint |
| mutates my list | `purity` never stated |
| pulled in a whole HTTP library | `roster` too loose |
| logs the API key | `security` never stated |

Fix the spec, not the output. A fixed output helps once; a fixed spec holds on every future run and
every model.

## 19. Model routing — designed for, not promised

Distinguishing 96% from 91% first-pass success needs hundreds of tasks **per model per task type**
before the difference is real. That volume does not exist at V1.0.

**Keep** the trace schema that would support routing: model, task type, outcome, cost, latency,
failure class. **Drop** the router from the roadmap until the data exists. Until then, model selection
is a configuration choice with a documented rationale, not an inference.

---

# Part V · Delivery

## 20. Milestones

| # | Milestone | Exit condition |
|---|---|---|
| **0** | Evaluation harness | fixtures, holdout policy, golden questions, counting rules, agreement checks, metrics wired to CI |
| **1** | Immutable scans | repository, scan, inventory, content hashes, commit binding |
| **2** | Language profiling + Python evidence extraction | detect single-language and polyglot repositories, route through the language-neutral adapter registry, and emit normalized Python symbols, imports, routes, source locations and diagnostics while reporting unsupported-language coverage |
| **2C** | Agent roster and orchestration contract | specify versioned agent profiles, deterministic task-roster derivation, typed handoffs, deny-by-default permissions, lifecycle, leases and activation gates without enabling code-writing agents |
| **3A** | Exact structural retrieval | scan-bound, case-sensitive symbol lookup and structured filters |
| **3B** | Evidence-graph traversal | bounded, cycle-safe incoming/outgoing traversal with unresolved targets preserved |
| **3C** | Full-text structural retrieval | bounded PostgreSQL full-text search over normalized documents |
| **4** | Assembly + Q&A | typed context package, coverage gate, claim validation, abstention, traces, review console |

M4A now implements the deterministic classifier, assembler, coverage gate,
structural renderer, claim controls, immutable persistence, cache, APIs, and
trace/feedback surface. M4B/M4C activation of the Repository Analyst and
Evidence Reviewer remains gated and disabled. The visual review console and
human release review are still open V0.1 work.

Milestones 0–4 are V0.1; 2C is a design checkpoint inside the Milestone 2/3
boundary. Realistically **three to four months** with a strong team, and only if §3 and
§4 are settled first.

Thereafter: V0.2 reference resolution and impact · V0.3 code-aware RAG, gated on A/B · V0.4
engineering context and rule discovery · V0.5 change planning · V0.6 execution contracts · V0.7 coding
agents · V0.8 verification · V0.9 adaptive repair · V1.0 ratchet at contract level.

## 21. V0.1 acceptance gates

Each is measured against the fixtures of §3, using the versioned counting rules.

```
symbol_precision            ≥ 0.95   on fx-small and fx-fastapi
symbol_recall               ≥ 0.95   on fx-small
import_edge_recall          ≥ 0.90   on all three Python fixtures
exact_lookup_case_safety    = 1.00   case variants never match accidentally
retrieval_scan_isolation    = 1.00   no result crosses the selected repository/scan
graph_cycle_safety          = 1.00   traversal terminates without duplicate expansion
graph_bound_enforcement     = 1.00   depth ≤ 3 and returned edges ≤ 500
unresolved_preservation     = 1.00   target text, status and reason survive retrieval
retrieval_determinism       = 1.00   identical inputs and evidence → identical ordering
full_text_case_precision    = 1.00   on the six labelled M3C development cases
full_text_case_recall       = 1.00   on the six labelled M3C development cases
full_text_scan_isolation    = 1.00   lexical results never cross repository/scan
full_text_safety_exclusion  = 1.00   generated, vendored and secret-flagged text is absent
full_text_postgres_contract = 1.00   tsvector, populated vectors, GIN and immutability pass
query_classifier_accuracy   = 1.00   supported/unsupported class and intent grammar
context_slot_map_accuracy   = 1.00   exact required slots for every golden question
pre_gate_model_call_count   = 0      unsupported or under-covered tasks stop before generation
context_budget_enforcement  = 1.00   every omission and truncation is stable and named
citation_validity           = 1.00   every path:line resolves in the selected scan
claim_linkage               = 1.00   every material claim SUPPORTED or labelled INFERENCE
abstention_correctness      = 1.00   on the unanswerable golden set
false_confident_answer_rate ≤ 0.02   the number that matters most
answer_coverage             report   share of answerable questions receiving a substantive answer
selective_accuracy          report   correctness on questions the system chooses to answer
abstention_precision/recall report   exposes both unsafe answers and over-abstention
determinism                 = 1.00   identical input → identical output via context cache
qualifier_preservation      = 1.00   no strengthening of labelled source qualifiers
holdout_regression          pass     no material release-gate regression on fx-holdout
```

`false_confident_answer_rate` is unsupported HIGH/DETERMINISTIC answers divided
by all HIGH/DETERMINISTIC answers.

Baselines recorded, not gated: scan time, query latency p50/p95, context tokens,
cost per query and evidence support precision. Incremental scan scope becomes a
V0.2 gate after full-scan correctness is established.

## 22. Security

Scanning must not execute repository code, must not run repository-provided
commands, must not send the whole repository to a model, and must preserve
repository boundaries. V0.1 explicitly configures maximum file size, file count,
total bytes, scan duration, symlink behavior, binary detection and encoding
fallback. Secret detection and redaction run at the context-projection boundary;
detector name, version and redaction count are traced without storing secret
values.

Future execution must be isolated, network-disabled by default, secret-free, resource-limited, must
log irreversible actions, and must gate them behind human approval. **Place the gate immediately
before the irreversible step**, not somewhere in the middle — and give the reviewer the artifact plus
its audit, not a bare "approve?".

## 23. Traces

Eight categories are present from V0.1: repository, retrieval, decision,
execution, verification, model interaction, human feedback, and learning.

```json
{
  "task_id": "...", "repository_id": "...", "scan_id": "...",
  "category": "EXECUTION | DECISION | VERIFICATION | MODEL_INTERACTION | HUMAN_FEEDBACK",
  "event_type": "graph_retrieval",
  "timestamp": "...",
  "metadata": {"root_symbol": "PaymentService", "direction": "reverse", "depth": 1}
}
```

Two properties make traces worth the storage:

- **Every branch records its reason**, not just its outcome.
- **Dropped material is logged.** Silent omission is what makes loss undetectable — if a slot was
  omitted or a candidate fell below a trust floor, the assembly log says so and why.
- **Corrections are linked.** Human feedback carries `correction_of`; the revised
  decision, changed artifacts, verification result and learning event share a
  correlation ID.

Model interaction traces record provider/model identity, request ID when
available, prompt-template and configuration versions, redacted input/output
hashes, evidence references, tool calls, tokens, latency, cost and validation
outcome. Raw prompts and outputs are disabled by default.

Store observable operational reasoning. Never store hidden model chain-of-thought, and never store
secrets.

---

# 24. Closing principle

The platform must improve for two independent reasons. Better models will help. But it must also
improve **when the model never changes**: more evidence, better resolution, better assembly, better
rules, better verification, better failure classification, better contracts.

> **Model intelligence is rented. Engineering intelligence is accumulated.**

The accumulation is the moat — which is why §18 starts it at V0.1 rather than V1.0.
