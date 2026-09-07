from __future__ import annotations

from uuid import uuid4

import pytest
from adaptive_platform.grounding import (
    Citation,
    CitationValidationInput,
    EvidenceSpan,
    LexicalSupportInput,
    QualifierPreservationInput,
    StructuralAssertion,
    StructuralEvidence,
    StructuralSupportInput,
    check_lexical_support,
    check_qualifier_preservation,
    check_structural_support,
    resolve_citation,
)


def _span(text: str = "payment_service may retry the checkout") -> EvidenceSpan:
    return EvidenceSpan(
        span_id="span-1",
        scan_id=SCAN_ID,
        path="app/checkout.py",
        start_line=10,
        end_line=12,
        start_column=0,
        end_column=40,
        text=text,
    )


SCAN_ID = uuid4()


def test_citation_resolves_only_a_complete_span_in_selected_scan() -> None:
    citation = Citation(SCAN_ID, "app/checkout.py", 10, 11, 2, 20)
    result = resolve_citation(CitationValidationInput(citation, SCAN_ID, (_span(),)))

    assert result.valid is True
    assert result.code == "CITATION_RESOLVED"
    assert result.evidence_span is not None
    assert result.evidence_span.span_id == "span-1"


def test_citation_rejects_cross_scan_and_out_of_range_evidence() -> None:
    citation = Citation(SCAN_ID, "app/checkout.py", 10, 13)
    missing = resolve_citation(CitationValidationInput(citation, SCAN_ID, (_span(),)))
    cross_scan = resolve_citation(CitationValidationInput(citation, uuid4(), (_span(),)))

    assert missing.code == "CITATION_SPAN_NOT_FOUND"
    assert cross_scan.code == "CITATION_SCAN_MISMATCH"


def test_lexical_check_normalizes_camel_snake_and_dotted_identifiers() -> None:
    result = check_lexical_support(
        LexicalSupportInput(
            entities=("PaymentService", "checkout.process_order"),
            evidence_spans=(_span("payment_service calls checkout.processOrder"),),
        )
    )

    assert result.supported is True
    assert result.missing_entities == ()


def test_lexical_check_names_missing_entities() -> None:
    result = check_lexical_support(
        LexicalSupportInput(("PaymentService", "RefundService"), (_span(),))
    )

    assert result.supported is False
    assert result.code == "LEXICAL_ENTITY_MISSING"
    assert result.missing_entities == ("RefundService",)


def test_structural_check_is_scan_bound_and_surfaces_conflict() -> None:
    assertion = StructuralAssertion("checkout.process", "CALLS", "payments.charge")
    supporting = StructuralEvidence(SCAN_ID, assertion, True, "span-1")
    contradiction = StructuralEvidence(SCAN_ID, assertion, False, "span-2")

    supported = check_structural_support(
        StructuralSupportInput(assertion, SCAN_ID, (supporting,))
    )
    conflicting = check_structural_support(
        StructuralSupportInput(assertion, SCAN_ID, (supporting, contradiction))
    )
    wrong_scan = check_structural_support(
        StructuralSupportInput(assertion, uuid4(), (supporting,))
    )

    assert supported.supported is True
    assert supported.evidence_span_ids == ("span-1",)
    assert conflicting.conflicting is True
    assert conflicting.code == "STRUCTURAL_EVIDENCE_CONFLICT"
    assert wrong_scan.code == "STRUCTURAL_EDGE_MISSING"


@pytest.mark.parametrize(
    ("source", "claim"),
    [
        ("The operation may succeed.", "The operation must succeed."),
        ("It usually runs.", "It always runs."),
        ("Some handlers validate input.", "All handlers validate input."),
        ("The module appears to cache data.", "The module is caching data."),
        ("This is likely safe.", "This is certainly safe."),
    ],
)
def test_qualifier_strengthening_is_rejected(source: str, claim: str) -> None:
    result = check_qualifier_preservation(
        QualifierPreservationInput(claim, (_span(source),))
    )

    assert result.preserved is False
    assert result.code == "QUALIFIER_STRENGTHENED"
    assert result.violations


def test_qualifier_preservation_accepts_the_same_hedge() -> None:
    result = check_qualifier_preservation(
        QualifierPreservationInput(
            "PaymentService may retry checkout.",
            (_span("PaymentService may retry checkout."),),
        )
    )

    assert result.preserved is True
