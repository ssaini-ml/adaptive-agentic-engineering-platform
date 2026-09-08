# Agent Roster and Orchestration Specification

**Document version 1.4** · implemented M4 grounding controls and honest model-agent boundary

## Status

This document maps every platform actor and orchestration node from Milestone 0
through V1.0, then defines the future agent control plane before agent execution
is implemented. Milestone 2C is specification-only: it does not authorize an
agent to modify a repository. M4 now implements the deterministic query,
assembly, coverage, citation, support and answer-decision controls. The two M4
model-agent profiles remain `DISABLED` until their provider-specific gates and
real human holdout review pass. Runtime activation follows §14 and §15.

The design deliberately treats an agent as a constrained role operating against
typed artifacts. It does not require a separate model, process, or service for
every role, and it does not permit free-form agents to coordinate through shared
conversation history.

## 1. Terms and boundaries

Two different rosters are required:

```text
resource roster   what repository entities and dependencies may be used
agent roster      which worker roles may act, in what order, with which permissions
```

The resource roster is derived from the immutable evidence graph:

```text
modules       resolved imports plus declared dependencies
symbols       symbols reachable from the approved change sites
exceptions    exception types defined or imported in the selected scan
commands      repository commands explicitly admitted by policy
forbidden     undeclared dependencies and out-of-contract resources
```

The agent roster is derived for one task from versioned agent profiles, the task
class, repository language coverage, risk, the selected scan, and the required
verification strategy.

Definitions:

- **AgentProfile** — a versioned, reusable capability and permission declaration.
- **TaskRoster** — immutable selection of profiles for one task and scan.
- **AgentRun** — one attempt by one selected profile against one typed handoff.
- **Handoff** — a schema-validated artifact, not conversational memory.
- **Orchestrator** — deterministic control logic that selects profiles, checks
  transitions, enforces leases and permissions, and records traces.
- **HumanApprover** — an external actor at an approval gate, not an autonomous agent.

### 1.1 Actor kinds

The complete roster contains more than LLM agents:

```text
SYSTEM_WORKER       deterministic application code
CONTROL_COMPONENT   deterministic policy, state or lease enforcement
MODEL_AGENT         model-backed role constrained by a profile and handoff
SANDBOXED_RUNNER    isolated command execution with an allowlist
HUMAN               reviewer or approver outside autonomous execution
```

Calling every worker an “agent” would hide important trust boundaries. The
scanner, profiler, AST extractor, graph traversal, policy engine and state
controller are system workers or control components. They do not receive an
`AgentProfile`, and a model cannot replace their enforcement responsibility.

### 1.2 Complete lifecycle actor roster

Status meanings:

```text
IMPLEMENTED   working code exists in the current repository
PARTIAL       some required behavior exists, but its milestone gate is incomplete
SPECIFIED     normative contract exists; runtime is not built
PLANNED       roadmap intent exists; detailed contract arrives before implementation
HUMAN_PENDING automated infrastructure exists but required human work is outstanding
```

| Stage | Actor | Kind | Responsibility | Current status |
|---|---|---|---|---|
| M0 | Fixture discovery worker | `SYSTEM_WORKER` | Discover manifest-declared evaluation fixtures | `IMPLEMENTED` |
| M0 | Evaluation runner | `SYSTEM_WORKER` | Validate labels and compute milestone gates | `IMPLEMENTED` |
| M0 | Independent label reviewers | `HUMAN` | Review golden labels and adjudicate disagreement | `HUMAN_PENDING` |
| M0 | Holdout custodian | `HUMAN` | Select, license and protect the release-only holdout | `HUMAN_PENDING` |
| M1 | Repository registrar | `SYSTEM_WORKER` | Validate and register an allowed local Git repository | `IMPLEMENTED` |
| M1 | Safe scan worker | `SYSTEM_WORKER` | Inventory files without executing repository code | `IMPLEMENTED` |
| M1 | Secret detector | `SYSTEM_WORKER` | Identify and count redactable secret patterns | `IMPLEMENTED` |
| M1 | Scan sealer | `CONTROL_COMPONENT` | Bind commit/fingerprint and enforce immutability | `IMPLEMENTED` |
| M2A | Language profiler | `SYSTEM_WORKER` | Detect all repository languages and coverage | `IMPLEMENTED` |
| M2A | Extractor registry/router | `CONTROL_COMPONENT` | Select one approved adapter per detected language | `IMPLEMENTED` |
| M2B | Python AST extractor | `SYSTEM_WORKER` | Emit normalized symbols, imports, routes and diagnostics | `IMPLEMENTED` |
| M2B | Structural relationship resolver | `SYSTEM_WORKER` | Resolve proven targets and preserve named uncertainty | `IMPLEMENTED` |
| M2B | Evidence persistence worker | `SYSTEM_WORKER` | Persist scan-bound immutable symbols and relationships | `IMPLEMENTED` |
| M2C | Lifecycle graph and roster specification | `CONTROL_COMPONENT` design | Define nodes, edges, roles, permissions and gates | `SPECIFIED` |
| M3A | Structural index maintainer | `SYSTEM_WORKER` | Maintain composite exact and graph access paths in the authoritative database | `IMPLEMENTED` |
| M3A | Exact retriever | `SYSTEM_WORKER` | Resolve case-sensitive names and filters deterministically within one scan | `IMPLEMENTED` |
| M3B | Graph traversal worker | `SYSTEM_WORKER` | Traverse bounded, cycle-safe incoming/outgoing evidence edges | `IMPLEMENTED` |
| M3C | Context-document builder and full-text retriever | `SYSTEM_WORKER` | Build bounded immutable text evidence and search it with PostgreSQL | `IMPLEMENTED` |
| M4 | Query classifier | `CONTROL_COMPONENT` | Select a supported query class, slots and bounded retrieval plan | `IMPLEMENTED` |
| M4 | Context assembler | `SYSTEM_WORKER` | Build typed, budgeted, hashed evidence packages | `IMPLEMENTED` |
| M4 | Coverage gate | `CONTROL_COMPONENT` | Decide readiness or abstention before generation | `IMPLEMENTED` |
| M4 | Citation and support validator | `CONTROL_COMPONENT` | Validate scan-bound citations, structure, lexical support and qualifiers | `IMPLEMENTED` |
| M4 | Answer finalizer | `CONTROL_COMPONENT` | Remove unsupported optional claims or abstain on essential failures | `IMPLEMENTED` |
| M4 | Repository Analyst | `MODEL_AGENT` | Propose structural explanations from an admitted context package | `SPECIFIED` (`DISABLED`) |
| M4 | Evidence Reviewer | `MODEL_AGENT` | Review only claims that deterministic validation cannot decide | `SPECIFIED` (`DISABLED`) |
| M4 | Review-console operator | `HUMAN` | Review abstentions and unresolved evidence | `PLANNED` |
| V0.2 | Call/reference resolver | `SYSTEM_WORKER` | Resolve bounded calls and references | `PLANNED` |
| V0.2 | Impact graph worker | `SYSTEM_WORKER` | Build affected-symbol/file projections | `PLANNED` |
| V0.2 | Incremental invalidator | `CONTROL_COMPONENT` | Invalidate evidence affected by repository changes | `PLANNED` |
| V0.3 | Semantic index worker | `SYSTEM_WORKER` | Maintain an optional derived semantic index | `PLANNED` |
| V0.3 | Hybrid retrieval evaluator | `SYSTEM_WORKER` | A/B semantic retrieval against structural baseline | `PLANNED` |
| V0.4 | Component/MRI builder | `SYSTEM_WORKER` | Derive components and engineering context | `PLANNED` |
| V0.4 | Candidate-rule reviewer | `HUMAN` | Approve or reject discovered engineering rules | `PLANNED` |
| V0.5 | Change Planner | `MODEL_AGENT` | Produce an ordered, evidence-bound change plan | `SPECIFIED` |
| V0.6 | Task classifier | `CONTROL_COMPONENT` | Classify work and risk | `SPECIFIED` |
| V0.6 | Resource-roster resolver | `CONTROL_COMPONENT` | Derive allowed repository entities | `SPECIFIED` |
| V0.6 | Agent-roster resolver | `CONTROL_COMPONENT` | Select compatible enabled profiles | `SPECIFIED` |
| V0.6 | Contract builder | `CONTROL_COMPONENT` | Materialize the scan-bound execution contract | `SPECIFIED` |
| V0.6 | Policy/state/lease controllers | `CONTROL_COMPONENT` | Enforce authority, transitions and write isolation | `SPECIFIED` |
| V0.6+ | Human Approver | `HUMAN` | Approve immediately before designated actions | `SPECIFIED` |
| V0.7 | Implementer | `MODEL_AGENT` | Apply one approved contract within exact scope | `SPECIFIED` |
| V0.8 | Verification runner | `SANDBOXED_RUNNER` | Run admitted checks reproducibly | `SPECIFIED` |
| V0.8 | Verifier | `MODEL_AGENT` or deterministic classifier | Interpret results without altering source | `SPECIFIED` |
| V0.9 | Failure classifier | `CONTROL_COMPONENT` | Assign one stable failure class | `SPECIFIED` |
| V0.9 | Repairer | `MODEL_AGENT` | Apply one admitted repair rung under a revised contract | `SPECIFIED` |
| V1.0 | Contract-learning worker | `SYSTEM_WORKER` | Propose ratchet changes from reviewed outcomes | `PLANNED` |
| V1.0 | Contract-rule approver | `HUMAN` | Approve generalized contract changes | `PLANNED` |

### 1.3 Three graphs, not one

The platform maintains three related graphs with different truth semantics:

| Graph | Nodes | Edges | Authority |
|---|---|---|---|
| Repository evidence graph | files, symbols, routes, documents, components | defines, imports, inherits, exposes, references, later calls/depends-on | Immutable scan evidence |
| Orchestration graph | typed workflow nodes and terminal states | guarded transitions carrying hashed handoffs | Versioned workflow definition plus state controller |
| Trace causality graph | events, model runs, feedback and corrections | parent, correction-of, supersedes and correlation links | Append-only runtime trace |

They may reference one another but must not be collapsed into one generic graph.
For example, an orchestration node may consume a repository-graph query result
and emit trace events, but neither its transition nor its trace becomes repository
evidence.

Repository evidence graph now and next:

```mermaid
flowchart LR
    Scan --> File
    File -->|symbol.file_id| Symbol
    Symbol -->|IMPORTS| TargetSymbol[Symbol or unresolved target]
    Symbol -->|INHERITS| TargetSymbol
    Symbol -->|EXPOSES| TargetSymbol
    Symbol -->|REFERENCES| TargetSymbol
    Symbol -. V0.2 CALLS .-> TargetSymbol
    Symbol -. V0.2 DEPENDS_ON .-> TargetSymbol
    M3A[RETRIEVE_EXACT implemented] -->|exact lookup| Symbol
    M3B[RETRIEVE_GRAPH implemented] -->|bounded traversal| TargetSymbol
    File -->|bounded approved text| Document
    M3C[RETRIEVE_FULL_TEXT implemented] -->|PostgreSQL lexical search| Document
```

The evidence nodes and structural edges are persisted in 2B. M3A/M3B add
case-sensitive lookup and bounded traversal behavior; they do not redefine
evidence truth. M3C now creates immutable context documents before scan sealing
and searches them without model reasoning.

End-to-end orchestration graph:

```mermaid
flowchart TD
    E0[EVALUATE_FIXTURES] -. release gate .-> R0[REGISTER_REPOSITORY]
    R0 --> S1[INVENTORY_SCAN]
    S1 --> L1[PROFILE_LANGUAGES]
    L1 --> L2[SELECT_EXTRACTORS]
    L2 --> X1[EXTRACT_EVIDENCE]
    X1 --> X2[PERSIST_EVIDENCE]
    X2 --> X3[BUILD_CONTEXT_DOCUMENTS]
    X3 --> S2[SEAL_SCAN]
    S2 --> Q1[CLASSIFY_QUERY]
    Q1 --> Q2A[RETRIEVE_EXACT]
    Q1 --> Q2B[RETRIEVE_GRAPH]
    Q1 --> Q2C[RETRIEVE_FULL_TEXT]
    Q2A --> Q3[ASSEMBLE_CONTEXT]
    Q2B --> Q3
    Q2C --> Q3
    Q3 --> Q4{COVERAGE_GATE}
    Q4 -->|insufficient| A0[ABSTAIN]
    Q4 -->|sufficient| A1[ANALYZE_OR_ANSWER]
    A1 --> A2[VALIDATE_CLAIMS]
    A2 -->|valid| C0[COMPLETE_READ_TASK]
    A2 -->|essential claim unsupported| A0
    C0 -. V0.5 change request .-> P1[PLAN_CHANGE]
    P1 --> P2[DERIVE_RESOURCE_ROSTER]
    P2 --> P3[DERIVE_AGENT_ROSTER]
    P3 --> P4[BUILD_EXECUTION_CONTRACT]
    P4 --> P5{APPROVAL_GATE}
    P5 -->|denied| B0[BLOCKED_OR_CANCELLED]
    P5 -->|approved or not required| W1[ACQUIRE_WRITE_LEASE]
    W1 --> W2[IMPLEMENT_CHANGE]
    W2 --> V1[VERIFY_CHANGE]
    V1 -->|pass| C1[COMPLETE_CHANGE_TASK]
    V1 -->|fail| F1[CLASSIFY_FAILURE]
    F1 -->|repair admitted| F2[SELECT_REPAIR_RUNG]
    F2 --> P4
    F1 -->|not admitted or exhausted| B0
```

Solid deterministic nodes through `COVERAGE_GATE`, plus the deterministic parts
of `VALIDATE_CLAIMS` and `FINALIZE_RESPONSE`, now have M0–M4 implementations.
The current APIs and services still invoke handlers directly rather than through
a generic graph runtime. `ANALYZE_OR_ANSWER` and model-assisted entailment do not
run while the two M4 model profiles are disabled. The change-execution branch
remains disabled until V0.5–V0.9.

## 2. Non-negotiable invariants

1. Every task roster is bound to `repository_id`, `scan_id`, commit identity, and
   configuration versions.
2. The orchestrator is deterministic for identical inputs and configuration.
3. Agent selection cannot upgrade unsupported language coverage to supported.
4. No agent receives permissions beyond both its profile and its execution contract.
5. Handoffs contain typed artifacts and references; raw multi-agent chat is not state.
6. Read-only work may run concurrently. One writer is the default and only one
   write lease may cover a file at a time.
7. A model never approves its own irreversible action or its own release gate.
8. Missing required inputs cause abstention or human escalation before execution.
9. Verification is performed against the resulting working-tree fingerprint.
10. Every selection, omission, permission decision, model call, correction,
    transition, and verification result is traceable without hidden chain-of-thought.

## 3. Control-plane components

| Component | Kind | Responsibility |
|---|---|---|
| Task classifier | Deterministic first, model-assisted only when measured | Assign the task class and risk flags |
| Roster resolver | Deterministic | Select eligible profiles and explain exclusions |
| State controller | Deterministic | Enforce allowed lifecycle transitions |
| Policy engine | Deterministic | Intersect profile, contract, repository and platform permissions |
| Lease manager | Deterministic | Prevent overlapping writes and stale execution |
| Context assembler | Deterministic pipeline | Produce typed, budgeted, scan-bound inputs |
| Model gateway | Controlled adapter | Execute approved model calls and record metadata |
| Verification runner | Sandboxed executor | Run contract-approved checks |
| Approval gateway | Human-controlled | Authorize designated high-risk or irreversible steps |

These components are not agents. They must not delegate policy decisions to the
same model whose output they constrain.

### 3.1 Workflow, node and edge contracts

An orchestration graph is a versioned definition, not model-generated control
flow:

```yaml
workflow:
  id: repository-change-lifecycle
  version: 1.0.0
  entry_nodes: [REGISTER_REPOSITORY]
  terminal_nodes: [COMPLETE, ABSTAINED, BLOCKED, FAILED, CANCELLED]
  nodes: [...]
  edges: [...]
  graph_hash: <sha256-of-canonical-definition>
```

Every node has one owner kind and typed boundaries:

```yaml
node:
  id: EXTRACT_PYTHON_EVIDENCE
  version: 1.0.0
  stage: M2B
  kind: SYSTEM_WORKER
  implementation_status: IMPLEMENTED
  handler_ref: adaptive_platform.extraction.python_ast.PythonAstExtractor

  input_schema: extraction-request-v1
  output_schema: extraction-result-v1
  preconditions: [scan_running, python_coverage_supported]
  guards: [source_hash_matches_inventory, repository_boundary_preserved]

  permissions:
    repository: INVENTORIED_FILES_READ_ONLY
    database: RUNNING_SCAN_EVIDENCE_WRITE
    commands: DENIED
    network: DENIED
    secrets: DENIED

  idempotency_key: [scan_id, extractor_name, extractor_version, configuration_version]
  timeout_seconds: 60
  success_event: extractor_completed
  failure_event: extractor_failed
```

Required node fields:

```text
id, version, stage, kind, implementation_status, handler_ref
input_schema, output_schema, preconditions, guards, permissions
idempotency_key, timeout/budget, success_event, failure_event
```

An edge carries a validated artifact and a deterministic condition:

```yaml
edge:
  id: coverage-complete-to-answer
  version: 1.0.0
  from: COVERAGE_GATE
  to: ANALYZE_OR_ANSWER
  priority: 10
  condition_code: ESSENTIAL_SLOTS_COMPLETE
  handoff_schema: context-package-v1
  guards: [same_task, same_scan, context_hash_verified]
  otherwise: coverage-incomplete-to-abstain
```

Required edge fields:

```text
id, version, from, to, priority, condition_code
handoff_schema, guards, otherwise/failure transition
```

The state controller evaluates edge conditions. A model may produce an artifact
consumed by a condition, but it cannot select an undeclared edge or create a node
at runtime. The only admitted cycle is a budgeted repair transition returning to
a revised contract; each pass receives a new run ID and artifact hashes.

### 3.2 Implemented node-to-code map

This is the logical node projection of the current code. It does not claim that
a generic orchestration engine already invokes these handlers.

| Node ID | Current implementation | Stored/produced artifact |
|---|---|---|
| `DISCOVER_FIXTURES` | `adaptive_platform.evaluation.loader.discover_fixture_dirs` | fixture set |
| `VALIDATE_FIXTURES` | `adaptive_platform.evaluation.loader.validate_fixture` | fixture summary/fingerprint |
| `EVALUATE_M0` | `adaptive_platform.evaluation.runner` | Milestone 0 report and trace |
| `EVALUATE_LANGUAGE_PROFILE` | `adaptive_platform.languages.evaluation` | Milestone 2A report and trace |
| `EVALUATE_PYTHON_EVIDENCE` | `adaptive_platform.extraction.evaluation` | predictions, 2B report and trace |
| `REGISTER_REPOSITORY` | `adaptive_platform.services.repositories.RepositoryService.register` | Repository record |
| `INVENTORY_SCAN` | `adaptive_platform.repository.scanner.scan_repository` | inventory result |
| `PROFILE_LANGUAGES` | `adaptive_platform.languages.profiler.profile_repository_languages` | language profile |
| `SELECT_EXTRACTORS` | `adaptive_platform.extraction.registry.ExtractorRegistry` | adapter descriptor/coverage |
| `LOAD_VERIFIED_SOURCE` | `adaptive_platform.extraction.source_loader.load_extraction_documents` | hash-verified documents |
| `EXTRACT_PYTHON_EVIDENCE` | `adaptive_platform.extraction.python_ast.PythonAstExtractor` | normalized extraction result |
| `PERSIST_EVIDENCE` | `adaptive_platform.services.repositories._persist_extraction_result` | symbols and relationships |
| `SEAL_SCAN` | `adaptive_platform.services.repositories.ScanService.execute` plus database guards | immutable completed scan |
| `BUILD_STRUCTURAL_INDEX` | `0004_structural_retrieval_indexes.py` (`0004_retrieval_indexes`) | composite exact/graph database indexes |
| `RETRIEVE_EXACT` | `adaptive_platform.retrieval.StructuralRetriever` | exact-symbol-result-v1 |
| `RETRIEVE_GRAPH` | `adaptive_platform.retrieval.StructuralRetriever` | graph-traversal-result-v1 |
| `EVALUATE_STRUCTURAL_RETRIEVAL` | `adaptive_platform.retrieval.evaluation` | M3A/M3B report and trace |
| `BUILD_CONTEXT_DOCUMENTS` | `adaptive_platform.retrieval.indexing.persist_context_documents` | immutable bounded ContextDocument records and search vectors |
| `RETRIEVE_FULL_TEXT` | `adaptive_platform.retrieval.FullTextRetriever` | full-text-result-v1 with cited ranked hits |
| `EVALUATE_FULL_TEXT_RETRIEVAL` | `adaptive_platform.retrieval.full_text_evaluation` | M3C PostgreSQL report and trace |
| `CLASSIFY_QUERY` | `adaptive_platform.context.classifier.QueryClassifier.classify` | query-contract-v1 with stable class, slots, retrieval plan and hash |
| `ASSEMBLE_CONTEXT` | `adaptive_platform.context.assembly.ContextAssembler.assemble` | context-package-v1 with typed slots, omissions, budgets and context hash |
| `COVERAGE_GATE` | `adaptive_platform.grounding.coverage.evaluate_coverage` | deterministic answer-or-abstain coverage decision and named gaps |
| `VALIDATE_CITATIONS` | `adaptive_platform.grounding.citations.resolve_citation` | scan-bound citation resolution result |
| `CHECK_CLAIM_SUPPORT` | `adaptive_platform.grounding.support` | structural, lexical and qualifier check results |
| `VALIDATE_CLAIMS` | `adaptive_platform.grounding.validator.DeterministicClaimValidator` | validated claims with verdicts, checks, evidence spans and gaps |
| `FINALIZE_RESPONSE` | `adaptive_platform.grounding.coverage.decide_answer` | answered, partial or abstained grounding decision |
| `PERSIST_GROUNDED_TASK` | `adaptive_platform.database.models` plus `0006_grounded_questions.py` | scan-bound task, context package, answer, claim and evidence-link records |
| `RECORD_TRACE` | `adaptive_platform.traces` plus `TraceEventRecord` | append-only trace event |

The M3A/M3B node contracts enforce a completed scan,
repository/scan ownership, case-sensitive exact identity, cycle-safe
breadth-first traversal, depth at most 3, result limit at most 500, unresolved
target preservation, and stable ordering. They are deterministic system workers,
not model agents. M3C adds bounded, code-aware PostgreSQL lexical retrieval,
conservative indexing exclusions, line citations, a 100-result cap, and the same
strict scan boundary. M4 adds deterministic classification, typed context
admission, pre-generation coverage, citation resolution, support checks,
qualifier preservation and essential-versus-optional claim decisions. These
controls are usable and testable without enabling either model profile.

### 3.3 Planned node map

| Stage | Node IDs | Owner kind | Primary output | Activation condition |
|---|---|---|---|---|
| M4 | `ANALYZE_OR_ANSWER` | `MODEL_AGENT` | proposed-answer-v1 | Analyst profile enabled only after coverage and provider-specific gates |
| M4 | model-assisted entailment within `VALIDATE_CLAIMS` | `MODEL_AGENT` | claim-review-v1 | Reviewer profile enabled only after labelled entailment and holdout gates |
| V0.2 | `RESOLVE_CALLS`, `BUILD_IMPACT_GRAPH`, `INVALIDATE_EVIDENCE` | system/control | impact-projection-v1 | reference-resolution evaluation passes |
| V0.3 | `BUILD_SEMANTIC_INDEX`, `RETRIEVE_SEMANTIC`, `COMPARE_HYBRID_AB` | `SYSTEM_WORKER` | semantic-comparison-v1 | semantic A/B admits provider |
| V0.4 | `DISCOVER_COMPONENTS`, `BUILD_REPOSITORY_MRI`, `PROPOSE_RULES` | system/model-assisted | engineering-context-v1 | candidate rules remain human-reviewed |
| V0.5 | `PLAN_CHANGE` | `MODEL_AGENT` | change-plan-v1 | grounded read path passes holdout |
| V0.6 | `CLASSIFY_TASK`, `DERIVE_RESOURCE_ROSTER`, `DERIVE_AGENT_ROSTER` | `CONTROL_COMPONENT` | task-roster-v1 | deterministic selection gates pass |
| V0.6 | `BUILD_EXECUTION_CONTRACT`, `POLICY_CHECK`, `APPROVAL_GATE` | control/human | execution-contract-v1 | required slots and approvals complete |
| V0.6 | `ACQUIRE_WRITE_LEASE`, `RELEASE_WRITE_LEASE` | `CONTROL_COMPONENT` | execution-lease-v1 | overlap and stale-scan gates pass |
| V0.7 | `IMPLEMENT_CHANGE` | `MODEL_AGENT` | implementation-result-v1 | constrained Implementer enabled |
| V0.8 | `RUN_VERIFICATION`, `INTERPRET_VERIFICATION` | runner/model or deterministic | verification-result-v1 | sandbox and command policy pass |
| V0.9 | `CLASSIFY_FAILURE`, `SELECT_REPAIR_RUNG` | `CONTROL_COMPONENT` | repair-request-v1 | stable failure taxonomy passes |
| V0.9 | `REPAIR_CHANGE` | `MODEL_AGENT` | implementation-result-v1 | revised contract and budget available |
| V1.0 | `AGGREGATE_OUTCOMES`, `PROPOSE_CONTRACT_RULE`, `APPROVE_CONTRACT_RULE` | system/human | versioned contract proposal | sufficient reviewed sample exists |

Every row expands into separately versioned node definitions before its runtime
milestone starts. Sharing a row does not permit one node to inherit another
node's permissions.

## 4. Canonical agent profiles

| Role | Purpose | Default permission | Activation |
|---|---|---|---|
| `REPOSITORY_ANALYST` | Explain structure, dependencies, evidence and uncertainty | Admitted context-package read only | Profile defined in M4; currently `DISABLED` |
| `EVIDENCE_REVIEWER` | Check claims not conclusively decided by deterministic validators | Proposed-answer and cited-evidence read only | Profile defined in M4; currently `DISABLED` |
| `CHANGE_PLANNER` | Produce an ordered, reviewable change plan | Proposal only | V0.5 |
| `IMPLEMENTER` | Apply an approved execution contract | Scoped workspace write | V0.7 |
| `VERIFIER` | Execute approved checks and classify failures | Approved commands; no source write | V0.8 |
| `SECURITY_REVIEWER` | Evaluate dependency, secret, network and permission risks | Repository and policy read | V0.6; mandatory by risk |
| `REPAIRER` | Apply one classified repair within a revised contract | Scoped workspace write | V0.9 |

`HUMAN_APPROVER` appears in workflows and traces but is not registered as an
agent profile. Retrieval, policy enforcement, lease management, and state
transitions remain deterministic platform capabilities rather than personas.

Logical roles may share one configured model. Conversely, a profile may have
language-specific variants such as `python-implementer`, `typescript-implementer`,
or `go-verifier`. The roster represents contracts and authority, not a claim that
more agents are inherently better.

### 4.1 M4 read-only profile definitions and activation boundary

The first two model profiles are defined but deliberately disabled:

| Profile | Required input | Output | Hard permission boundary | Current status |
|---|---|---|---|---|
| `repository-analyst-structural@1.0.0` | `repository-analysis-request-v1` wrapping a validated `query-contract-v1` and coverage-approved `context-package-v1` | `proposed-answer-v1` containing atomic claims and evidence references | no filesystem, commands, repository mutation, secrets, external side effects or tool-selected retrieval | `DISABLED` |
| `evidence-reviewer-structural@1.0.0` | `claim-review-request-v1` wrapping `proposed-answer-v1`, deterministic check results and the exact cited evidence projection | `claim-review-v1` for claims explicitly routed to model-assisted entailment | no retrieval widening, filesystem, commands, mutation, approval authority, secrets or external side effects | `DISABLED` |

The model gateway, not either profile, owns provider connectivity and must expose
only the admitted typed artifact. The gateway boundary rejects a missing wrapper
field, mismatched schema or content hash, missing passing gate evidence references,
incomplete provider metadata, or invalid token counts before accepting a result.
A provider call cannot add evidence, change a
coverage decision, select a workflow edge or mark its own claim valid. The
deterministic validator and finalizer remain authoritative even after profiles
are enabled.

Activation is provider- and model-configuration-specific. It requires all of the
following rather than merely passing unit tests with a fake gateway:

```text
M3 retrieval gates pass
M4 classification, assembly, coverage and deterministic validation gates pass
the configured provider/model passes the labelled answer and entailment cases
false_confident_answer_rate <= 0.02 for that configuration
model-context and read-only permission boundaries pass
model-interaction trace completeness = 1.00
the real release-only holdout is reviewed by the required humans
```

Until those conditions are recorded, the platform may classify, assemble,
abstain and validate deterministic claim fixtures, but it must not describe a
model-generated repository answer as an active M4 capability. This boundary does
not block development and testing through a controlled fake gateway, and it does
not activate the Planner, Implementer, Verifier or Repairer.

## 5. AgentProfile contract

```yaml
agent_profile:
  id: python-change-implementer
  version: 1.0.0
  role: IMPLEMENTER
  status: DISABLED               # ENABLED only at its activation milestone

  supported_task_classes: [DEPENDENCY_UPGRADE, BUG_FIX, REFACTOR]
  supported_languages: [Python]
  required_language_coverage: SUPPORTED
  capabilities: [edit_source, edit_tests, edit_configuration]

  required_inputs:
    - scan_binding
    - approved_plan
    - execution_contract
    - resource_roster
    - evidence_package

  output_schema: implementation-result-v1

  permissions:
    filesystem: CONTRACT_PATHS_ONLY
    commands: CONTRACT_ALLOWLIST_ONLY
    network: DENIED
    secrets: DENIED
    external_side_effects: DENIED

  budgets:
    max_model_calls: 4
    max_tool_calls: 40
    max_wall_seconds: 900

  required_gates:
    before: [scan_current, contract_complete, human_approval_if_required]
    after: [patch_in_scope, resource_roster_compliant, verification_required]

  model_policy_ref: default-coding-model-v1
  prompt_template_version: implementer-v1
  profile_hash: <sha256-of-canonical-profile>
```

Required profile fields:

```text
id, version, role, status
supported_task_classes, supported_languages, required_language_coverage
capabilities, required_inputs, output_schema
permissions, budgets, required_gates
model_policy_ref, prompt_template_version, profile_hash
```

A model name is configuration, not agent identity. Updating the model without
changing behavior may update the model policy; changing permissions, inputs,
outputs, or gates requires a profile version change.

## 6. TaskRoster contract

```yaml
task_roster:
  id: <uuid>
  version: 1.0.0
  task_id: <uuid>
  repository_id: <uuid>
  scan_id: <uuid>
  commit_hash: <sha>
  working_tree_fingerprint: <sha256>
  task_class: DEPENDENCY_UPGRADE
  risk: MEDIUM

  selected:
    - sequence: 1
      profile: repository-analyst@1.0.0
      reason_code: STRUCTURAL_CONTEXT_REQUIRED
    - sequence: 2
      profile: change-planner@1.0.0
      reason_code: MULTI_FILE_CHANGE
    - sequence: 3
      profile: python-change-implementer@1.0.0
      reason_code: PRIMARY_LANGUAGE_SUPPORTED
    - sequence: 4
      profile: verifier@1.0.0
      reason_code: EXECUTION_REQUIRES_VERIFICATION

  excluded:
    - profile: typescript-change-implementer@1.0.0
      reason_code: LANGUAGE_NOT_IN_CHANGE_SCOPE

  handoffs:
    - from: repository-analyst@1.0.0
      to: change-planner@1.0.0
      schema: repository-analysis-v1

  concurrency_groups:
    read: [repository-analyst@1.0.0, security-reviewer@1.0.0]
    write: [python-change-implementer@1.0.0]

  required_approvals: []
  roster_hash: <sha256-of-canonical-roster>
  resolver_version: roster-resolver-v1
```

Once execution begins, a roster is immutable. Reselection creates a new roster
version and records which prior roster it supersedes.

## 7. Deterministic roster derivation

Inputs:

```text
task class and requested outcome
selected immutable scan
language profile and extractor coverage
framework and component evidence
files and symbols in the proposed change scope
risk flags and required approvals
available enabled AgentProfiles
platform and repository policy
required post-change checks
```

Algorithm:

1. Reject a missing, incomplete, or stale scan binding.
2. Classify the task and identify required capabilities.
3. Determine languages and components touched by the proposed scope.
4. Exclude disabled profiles and profiles lacking required capabilities.
5. Exclude language-specific profiles unless every changed language meets the
   profile's required coverage.
6. Add mandatory review roles from risk policy.
7. Add a verifier whenever any write role is selected.
8. Intersect permissions across platform policy, repository policy, profile, and
   execution contract; the narrowest value wins.
9. Produce selected and excluded lists with stable reason codes.
10. Canonicalize, hash, persist, and trace the result.

Selection tie-breaking is stable: explicit repository policy, then highest
compatible profile version, then lexicographic profile ID. Model-based dynamic
routing is forbidden until outcome volume is statistically sufficient.

If a task touches a language whose required adapter is `PARTIAL`, `UNSUPPORTED`,
or `FAILED`, the resolver may select read-only analysis with explicit gaps but
must not select a language-specific writer.

## 8. Orchestration lifecycle

```text
CREATED
  → CLASSIFIED
  → ROSTER_DERIVED
  → CONTEXT_READY
  → PLANNED
  → CONTRACT_READY
  → AWAITING_APPROVAL       when policy requires it
  → EXECUTING
  → VERIFYING
  → COMPLETED
```

Terminal or branch states:

```text
ABSTAINED       evidence or required slots are insufficient
BLOCKED         external authority or unavailable capability is required
FAILED          terminal technical failure with no admitted repair
REPAIR_PENDING  a classified failure has an eligible repair rung
CANCELLED       human or policy cancellation before an irreversible action
```

Only the deterministic state controller changes task state. An agent may propose
a transition but cannot commit it. Every transition declares its required
artifacts and guards. For example, `EXECUTING → VERIFYING` requires a valid
implementation result, a patch limited to approved files, an unchanged write
lease, and a captured post-write fingerprint.

## 9. Typed handoffs

Canonical handoff schemas:

| Artifact | Producer | Consumer | Minimum content |
|---|---|---|---|
| `repository-analysis-v1` | Analyst | Planner | scan binding, findings, evidence refs, uncertainty, gaps |
| `change-plan-v1` | Planner | Human/contract builder | ordered changes, files, symbols, risks, checks, assumptions |
| `execution-contract-v1` | Contract builder | Implementer | goal slots, resource roster, permissions, forbidden actions, checks |
| `implementation-result-v1` | Implementer | Verifier | patch hash, changed files, decisions, gaps, post-write fingerprint |
| `verification-result-v1` | Verifier | State controller/repair | command refs, outcomes, failure class, evidence, reproducibility |
| `repair-request-v1` | State controller | Repairer | failed slot, failure class, prior attempt refs, selected rung, revised limits |

Every handoff includes schema version, producer profile/run, task and roster IDs,
scan binding, input artifact hashes, created time, and content hash. A consumer
rejects missing or mismatched fields rather than filling them silently.

## 10. Permission model

Permissions are deny-by-default and independently enforced outside the model.

| Capability | Analyst | Planner | Implementer | Verifier | Security reviewer | Repairer |
|---|---:|---:|---:|---:|---:|---:|
| Read approved repository files | Yes | Yes | Yes | Yes | Yes | Yes |
| Read evidence graph | Yes | Yes | Yes | Yes | Yes | Yes |
| Modify source/configuration | No | No | Contract paths | No | No | Contract paths |
| Run repository commands | No | No | Exceptional allowlist | Check allowlist | No | Repair allowlist |
| Network access | No | No | Denied by default | Denied by default | Metadata proxy only if approved | Denied by default |
| Read secrets | No | No | No | No | No secret values | No |
| Approve irreversible action | No | No | No | No | No | No |

An allowlist names the executable and fixed argument pattern. Repository-provided
commands are data until admitted by policy. Shell expansion, undeclared package
installation, external messages, deployment, merge, publication, and destructive
operations require explicit contracts and, where applicable, immediate human approval.

## 11. Concurrency and workspace isolation

- Multiple read-only roles may run concurrently only against the same `scan_id`.
- The default topology has one implementer or repairer at a time.
- A write lease covers repository ID, workspace ID, roster ID, contract ID, and
  exact file set.
- Overlapping file leases are rejected, including leases from different tasks.
- Non-overlapping writers remain disabled until merge-conflict, shared-build-state,
  and verification-isolation evaluations justify them.
- Verification begins only after the writer releases its active mutation phase
  and the resulting fingerprint is captured.
- A moved tree invalidates the lease and returns the task to planning; agents
  cannot rebase, merge, or widen scope autonomously.

## 12. Failure and repair routing

The verifier or policy engine assigns one stable failure class:

```text
SPECIFICATION_GAP
IMPLEMENTATION_ERROR
CONTEXT_MISSING
ARCHITECTURE_VIOLATION
SECURITY_VIOLATION
DEPENDENCY_VIOLATION
TEST_FAILURE
MODEL_LIMITATION
CONFLICTING_REQUIREMENTS
STALE_SCAN
PERMISSION_DENIED
```

The state controller selects at most one next rung: restate, name the failing
slot, provide a counterexample, expand admitted context, switch configured model,
or request human intervention. `CONTEXT_MISSING` is the only class that can widen
context automatically, and it still cannot widen filesystem or network authority.

A repair run never inherits write permission implicitly. It requires a revised
contract, a new run ID, remaining budget, and the same or narrower resource roster.

## 13. Trace requirements

Required events include:

```text
exact_symbol_retrieval_completed
graph_traversal_completed
task_classified
context_candidate_admitted | context_candidate_omitted
context_assembled
coverage_gate_passed | coverage_gate_failed
claim_validation_completed
answer_finalized | answer_abstained
context_cache_hit | context_cache_miss
agent_profile_considered
agent_profile_selected
agent_profile_excluded
task_roster_created
handoff_validated | handoff_rejected
permission_granted | permission_denied
write_lease_acquired | write_lease_released | write_lease_rejected
agent_run_started | agent_run_completed | agent_run_failed
orchestration_transition
verification_completed
repair_rung_selected
human_approval_requested | human_approval_recorded
```

Traces record profile/model/configuration versions, reason codes, artifact hashes,
evidence references, tool-call summaries, tokens, cost, latency, corrections and
validation outcomes. They do not store hidden chain-of-thought, unredacted
secrets, or unrestricted raw prompts by default.

## 14. Evaluation gates

Before either M4 read-only model profile is enabled for a concrete provider and
model configuration:

```text
query_classification_accuracy            = 1.00 on admitted V0.1 classes
required_slot_mapping_accuracy           = 1.00
context_scan_isolation                   = 1.00
context_budget_enforcement               = 1.00
context_determinism                      = 1.00
context_omission_trace_completeness      = 1.00
coverage_gate_correctness                = 1.00
model_calls_when_coverage_incomplete     = 0
citation_validity                        = 1.00
claim_linkage                            = 1.00
qualifier_preservation                   = 1.00
agent_read_only_enforcement              = 1.00
agent_context_boundary_enforcement       = 1.00
model_interaction_trace_completeness     = 1.00
false_confident_answer_rate             <= 0.02
provider_specific_holdout_review         = pass
```

Passing deterministic M4 unit tests or fake-gateway tests does not satisfy the
last two gates and does not change a profile from `DISABLED` to `ENABLED`.

Before any write-capable agent is enabled:

```text
roster_derivation_determinism          = 1.00
required_role_recall                   = 1.00
forbidden_role_selection_rate          = 0.00
unsupported_language_writer_rate       = 0.00
permission_enforcement                 = 1.00
stale_scan_rejection                   = 1.00
overlapping_write_lease_rejection      = 1.00
typed_handoff_completeness             = 1.00
verification_required_after_write      = 1.00
orchestration_trace_completeness       = 1.00
unauthorized_irreversible_action_rate  = 0.00
```

Fixtures must include single-language, polyglot, stale-scan, missing-context,
overlapping-write, malicious-instruction, unsupported-language, failed-check,
and human-approval cases. A general multi-agent demonstration does not satisfy
these gates.

## 15. Activation roadmap

| Stage | What becomes active | Required predecessor |
|---|---|---|
| Milestone 2C | Profiles, roster, handoff, permission, lifecycle and gate specification | 2B evidence contract |
| Milestones 3A–3B | Deterministic exact and graph retrieval nodes; no model agent | 2B evidence contract |
| Milestone 3C | Deterministic PostgreSQL full-text retrieval node | M3A/M3B retrieval gates |
| Milestone 4A | Deterministic classifier, context assembler, coverage gate, claim validator and finalizer | M3 structural and full-text retrieval contracts |
| Milestone 4B | Read-only Repository Analyst profile for one provider/model configuration | Grounded assembly gates, provider-specific answer gates and real human holdout review |
| Milestone 4C | Model-assisted Evidence Reviewer profile for undecidable claims | Labelled entailment, qualifier, trace and independence gates for that configuration |
| V0.5 | Change Planner | Validated repository context and plan schema |
| V0.6 | Roster resolver, state controller, leases, policy engine, execution contracts | Planning evaluation |
| V0.7 | One constrained Implementer per contract | V0.6 control-plane gates |
| V0.8 | Sandboxed Verifier | Approved command policy and reproducibility gates |
| V0.9 | Repairer and repair state transitions | Failure classifier and repair-budget gates |

Agent profiles may be authored and stored before activation, but their status
must remain `DISABLED`. Milestone 2C completion therefore means the design is
falsifiable and implementation-ready—not that autonomous modification is safe.

## 16. Framework-upgrade example

For a future Rasa-style dependency upgrade:

```text
scan and language profile
  → Repository Analyst identifies Python modules, manifests and affected symbols
  → Security Reviewer is selected if dependencies or network metadata are involved
  → Change Planner produces ordered manifest, source, migration and test steps
  → Human approval occurs if dependency or external-action policy requires it
  → one Python Implementer receives only approved paths and the resource roster
  → Verifier runs only the admitted upgrade checks
  → failure is classified; Repairer is selected only with a revised contract
```

If the same repository contains unsupported TypeScript files in the requested
change scope, the roster resolver blocks a write roster for that scope. It does
not let the Python implementer guess across the unsupported boundary.

## 17. Design decision

The platform adopts a small canonical roster, dynamically projected to each task,
rather than a standing society of agents. Roles are selected because a contract
requires a capability, not because every task should involve every persona. This
retains the useful specialization of the Rasa-upgrade workflow while preventing
free-form agent coordination from bypassing evidence, permissions, or verification.
