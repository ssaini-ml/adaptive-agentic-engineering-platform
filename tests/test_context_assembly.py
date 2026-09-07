from uuid import UUID

import pytest
from adaptive_platform.context import (
    AssemblyBudget,
    ContextAssembler,
    ContextAssemblyError,
    CoverageDecision,
    EvidenceCandidate,
    EvidenceCompleteness,
    EvidenceProvenance,
    EvidenceStatus,
    OmissionReason,
    QueryClassifier,
    RetrievalMethod,
    ScanBinding,
    SlotName,
    SlotStatus,
    TrustClass,
    deterministic_token_count,
)

BINDING = ScanBinding(
    repository_id=UUID("10000000-0000-0000-0000-000000000001"),
    scan_id=UUID("10000000-0000-0000-0000-000000000002"),
)
OTHER_SCAN = UUID("10000000-0000-0000-0000-000000000003")


def _candidate(
    item_id: str,
    slot: SlotName,
    content: str,
    *,
    scan_id=BINDING.scan_id,
    status=EvidenceStatus.RECORDED,
    trust=TrustClass.EXACT_SYMBOL,
    rank=1,
    input_refs=(),
    completeness=EvidenceCompleteness.COMPLETE,
    resolution_status=None,
):
    return EvidenceCandidate(
        item_id=item_id,
        slot=slot,
        content=content,
        status=status,
        trust=trust,
        provenance=EvidenceProvenance(
            scan_id=scan_id,
            source_kind=RetrievalMethod.EXACT,
            artifact_id=item_id,
            file_path="app/service.py",
            start_line=4,
            end_line=4,
            producer="python-ast",
            producer_version="1",
            input_refs=input_refs,
            resolution_status=resolution_status,
        ),
        retrieval_rank=rank,
        completeness=completeness,
        selection_reason="Exact definition matched the requested symbol.",
    )


def test_assembler_is_deterministic_and_trust_ordered():
    contract = QueryClassifier().classify(BINDING, "Where is CustomerService defined?")
    lexical = _candidate(
        "lexical",
        SlotName.EXACT_SYMBOL,
        "class CustomerService: pass",
        trust=TrustClass.FULL_TEXT,
        rank=1,
    )
    exact = _candidate("exact", SlotName.EXACT_SYMBOL, "CustomerService at line 4", rank=2)

    first = ContextAssembler().assemble(contract, [lexical, exact])
    second = ContextAssembler().assemble(contract, [exact, lexical])

    assert first.context_hash == second.context_hash
    assert [item.item_id for item in first.slots[0].items] == ["exact", "lexical"]
    assert first.coverage_decision is CoverageDecision.READY
    assert first.gaps == ()


def test_assembler_names_scan_and_budget_omissions_and_gap():
    contract = QueryClassifier().classify(BINDING, "Where is CustomerService defined?")
    wrong_scan = _candidate(
        "wrong-scan", SlotName.EXACT_SYMBOL, "CustomerService", scan_id=OTHER_SCAN
    )
    oversized = _candidate(
        "too-large", SlotName.EXACT_SYMBOL, "one two three four five six seven"
    )
    package = ContextAssembler().assemble(
        contract,
        [wrong_scan, oversized],
        AssemblyBudget(max_tokens=100, max_items=2, max_tokens_per_slot=5),
    )

    assert package.coverage_decision is CoverageDecision.ABSTAIN
    assert package.gaps == (SlotName.EXACT_SYMBOL,)
    assert package.slots[0].status is SlotStatus.OMITTED_BUDGET
    assert {item.reason for item in package.omissions} == {
        OmissionReason.WRONG_SCAN,
        OmissionReason.SLOT_TOKEN_BUDGET,
    }


def test_generated_content_is_labeled_but_cannot_fill_required_evidence_slot():
    contract = QueryClassifier().classify(BINDING, "Where is CustomerService defined?")
    generated = _candidate(
        "generated",
        SlotName.EXACT_SYMBOL,
        "CustomerService is probably in services.py",
        status=EvidenceStatus.GENERATED,
        trust=TrustClass.GENERATED,
    )

    package = ContextAssembler().assemble(contract, [generated])

    assert package.slots[0].items[0].status is EvidenceStatus.GENERATED
    assert package.slots[0].status is SlotStatus.MISSING
    assert package.coverage_decision is CoverageDecision.ABSTAIN


def test_declared_slot_order_controls_admission_under_global_item_budget():
    contract = QueryClassifier().classify(
        BINDING, "Which files import PaymentService, and which are tests?"
    )
    exact = _candidate("exact", SlotName.EXACT_SYMBOL, "PaymentService")
    category = _candidate("category", SlotName.FILE_CATEGORIES, "tests/test_payment.py")
    package = ContextAssembler().assemble(
        contract,
        [category, exact],
        AssemblyBudget(max_tokens=100, max_items=1, max_tokens_per_slot=50),
    )

    assert package.slots[0].items[0].item_id == "exact"
    assert package.omissions[0].item_id == "category"
    assert package.omissions[0].reason is OmissionReason.ITEM_LIMIT


def test_derived_content_requires_input_provenance():
    contract = QueryClassifier().classify(BINDING, "Where is CustomerService defined?")
    missing_refs = _candidate(
        "derived",
        SlotName.EXACT_SYMBOL,
        "Derived location",
        status=EvidenceStatus.DERIVED,
        trust=TrustClass.DERIVED,
    )
    package = ContextAssembler().assemble(contract, [missing_refs])

    assert package.omissions[0].reason is OmissionReason.INSUFFICIENT_PROVENANCE
    assert package.gaps == (SlotName.EXACT_SYMBOL,)


@pytest.mark.parametrize(
    ("completeness", "expected"),
    [
        (EvidenceCompleteness.AMBIGUOUS, SlotStatus.AMBIGUOUS),
        (EvidenceCompleteness.PARTIAL, SlotStatus.UNFILLABLE),
        (EvidenceCompleteness.UNRESOLVED, SlotStatus.UNFILLABLE),
    ],
)
def test_ambiguous_partial_and_unresolved_evidence_do_not_pass_coverage(
    completeness, expected
):
    contract = QueryClassifier().classify(BINDING, "Where is CustomerService defined?")
    candidate = _candidate(
        "uncertain",
        SlotName.UNIQUE_TARGET,
        "CustomerService candidate",
        completeness=completeness,
    )

    package = ContextAssembler().assemble(contract, [candidate])

    assert package.slots[0].status is expected
    assert package.coverage_decision is CoverageDecision.ABSTAIN


def test_multiple_exact_targets_are_ambiguous():
    contract = QueryClassifier().classify(BINDING, "Where is CustomerService defined?")
    first = _candidate("one", SlotName.UNIQUE_TARGET, "app.one.CustomerService")
    second = _candidate("two", SlotName.UNIQUE_TARGET, "app.two.CustomerService", rank=2)

    package = ContextAssembler().assemble(contract, [first, second])

    assert package.slots[0].status is SlotStatus.AMBIGUOUS
    assert package.gaps == (SlotName.UNIQUE_TARGET,)


def test_recorded_empty_result_can_fill_a_list_slot():
    contract = QueryClassifier().classify(BINDING, "Which routes are defined?")
    empty = _candidate(
        "route-query-empty",
        SlotName.ROUTE_SYMBOLS,
        "",
        completeness=EvidenceCompleteness.EMPTY,
    )

    package = ContextAssembler().assemble(contract, [empty])

    assert package.slots[0].status is SlotStatus.FILLED_EMPTY
    assert package.coverage_decision is CoverageDecision.READY


def test_empty_unique_target_is_unfillable():
    contract = QueryClassifier().classify(BINDING, "Where is CustomerService defined?")
    empty = _candidate(
        "target-query-empty",
        SlotName.UNIQUE_TARGET,
        "",
        completeness=EvidenceCompleteness.EMPTY,
    )

    package = ContextAssembler().assemble(contract, [empty])

    assert package.slots[0].status is SlotStatus.UNFILLABLE
    assert package.coverage_decision is CoverageDecision.ABSTAIN


def test_heuristic_graph_evidence_is_treated_as_partial_even_if_unmarked():
    contract = QueryClassifier().classify(BINDING, "Which files import PaymentService?")
    target = _candidate("target", SlotName.UNIQUE_TARGET, "PaymentService")
    heuristic = _candidate(
        "edge",
        SlotName.IMPORT_EDGES,
        "app/main.py imports PaymentService",
        trust=TrustClass.HEURISTIC_GRAPH,
    )

    package = ContextAssembler().assemble(contract, [target, heuristic])

    assert package.slots[1].items[0].completeness is EvidenceCompleteness.PARTIAL
    assert package.slots[1].status is SlotStatus.UNFILLABLE
    assert package.coverage_decision is CoverageDecision.ABSTAIN


def test_recorded_resolution_status_overrides_overconfident_candidate_default():
    contract = QueryClassifier().classify(BINDING, "Which files import PaymentService?")
    target = _candidate("target", SlotName.UNIQUE_TARGET, "PaymentService")
    unresolved = _candidate(
        "edge",
        SlotName.IMPORT_EDGES,
        "PaymentService",
        trust=TrustClass.RESOLVED_GRAPH,
        resolution_status="UNRESOLVED",
    )

    package = ContextAssembler().assemble(contract, [target, unresolved])

    assert package.slots[1].items[0].completeness is EvidenceCompleteness.UNRESOLVED
    assert package.slots[1].status is SlotStatus.UNFILLABLE


def test_item_limit_and_duplicate_are_explicit():
    contract = QueryClassifier().classify(BINDING, "Where is CustomerService defined?")
    first = _candidate("first", SlotName.EXACT_SYMBOL, "one")
    duplicate = _candidate("first", SlotName.EXACT_SYMBOL, "one")
    second = _candidate("second", SlotName.EXACT_SYMBOL, "two", rank=2)
    package = ContextAssembler().assemble(
        contract,
        [second, duplicate, first],
        AssemblyBudget(max_tokens=100, max_items=1, max_tokens_per_slot=50),
    )

    assert package.item_count == 1
    assert {omission.reason for omission in package.omissions} == {
        OmissionReason.DUPLICATE,
        OmissionReason.ITEM_LIMIT,
    }


def test_unsupported_contract_abstains_even_if_a_candidate_is_present():
    contract = QueryClassifier().classify(BINDING, "Why did the team choose Python?")
    recorded = _candidate(
        "decision",
        SlotName.RECORDED_DECISION,
        "Python was chosen in ADR-1.",
    )

    package = ContextAssembler().assemble(contract, [recorded])

    assert package.gaps == ()
    assert package.coverage_decision is CoverageDecision.ABSTAIN


def test_deterministic_token_counter_and_budget_validation():
    assert deterministic_token_count("CustomerService(path='/x')") == 9
    contract = QueryClassifier().classify(BINDING, "Where is CustomerService defined?")
    with pytest.raises(ContextAssemblyError):
        ContextAssembler().assemble(
            contract,
            [],
            AssemblyBudget(max_tokens=100, max_items=1, max_tokens_per_slot=101),
        )
