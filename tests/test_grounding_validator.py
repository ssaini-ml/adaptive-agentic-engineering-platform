from __future__ import annotations

from uuid import uuid4

from adaptive_platform.grounding import (
    CheckName,
    CheckStatus,
    Citation,
    ClaimDraft,
    ClaimImportance,
    ClaimVerdict,
    DeterministicClaimValidator,
    EvidenceSpan,
    StructuralAssertion,
    StructuralEvidence,
)

SCAN_ID = uuid4()
SPAN = EvidenceSpan(
    span_id="checkout-call",
    scan_id=SCAN_ID,
    path="app/checkout.py",
    start_line=7,
    end_line=9,
    text="def process_order():\n    return PaymentService.charge()\n",
)
CITATION = Citation(SCAN_ID, "app/checkout.py", 7, 9)
ASSERTION = StructuralAssertion("checkout.process_order", "CALLS", "PaymentService.charge")


def _claim(**changes: object) -> ClaimDraft:
    values: dict[str, object] = {
        "claim_id": "claim-1",
        "text": "process_order calls PaymentService.charge.",
        "importance": ClaimImportance.ESSENTIAL,
        "citations": (CITATION,),
        "entities": ("process_order", "PaymentService.charge"),
        "structural_assertion": ASSERTION,
    }
    values.update(changes)
    return ClaimDraft(**values)  # type: ignore[arg-type]


def test_validator_accepts_cited_lexical_and_structural_support_deterministically() -> None:
    validator = DeterministicClaimValidator(
        selected_scan_id=SCAN_ID,
        evidence_spans=(SPAN,),
        structural_evidence=(StructuralEvidence(SCAN_ID, ASSERTION, True, SPAN.span_id),),
    )

    first = validator.validate(_claim())
    second = validator.validate(_claim())

    assert first == second
    assert first.verdict == ClaimVerdict.SUPPORTED
    assert first.evidence_span_ids == ("checkout-call",)
    assert all(check.status != CheckStatus.FAIL for check in first.checks)


def test_validator_rejects_invalid_citation_and_missing_structural_edge() -> None:
    validator = DeterministicClaimValidator(
        selected_scan_id=SCAN_ID,
        evidence_spans=(SPAN,),
    )
    wrong_scan_claim = _claim(
        citations=(Citation(uuid4(), "app/checkout.py", 7, 9),),
    )

    result = validator.validate(wrong_scan_claim)

    assert result.verdict == ClaimVerdict.UNSUPPORTED
    assert {gap.code for gap in result.gaps} == {
        "CITATION_SCAN_MISMATCH",
        "STRUCTURAL_EDGE_MISSING",
        "LEXICAL_ENTITY_MISSING",
    }


def test_validator_surfaces_structural_conflict() -> None:
    validator = DeterministicClaimValidator(
        selected_scan_id=SCAN_ID,
        evidence_spans=(SPAN,),
        structural_evidence=(StructuralEvidence(SCAN_ID, ASSERTION, False, SPAN.span_id),),
    )

    result = validator.validate(_claim())

    assert result.verdict == ClaimVerdict.CONFLICTING
    assert "STRUCTURAL_EVIDENCE_CONFLICT" in {gap.code for gap in result.gaps}


def test_inference_requires_an_inline_label() -> None:
    validator = DeterministicClaimValidator(selected_scan_id=SCAN_ID, evidence_spans=(SPAN,))
    unlabeled = _claim(
        requested_verdict=ClaimVerdict.INFERENCE,
        structural_assertion=None,
        inference_labeled_inline=False,
    )
    labeled = _claim(
        requested_verdict=ClaimVerdict.INFERENCE,
        structural_assertion=None,
        inference_labeled_inline=True,
    )

    rejected = validator.validate(unlabeled)
    accepted = validator.validate(labeled)

    assert rejected.verdict == ClaimVerdict.UNSUPPORTED
    assert accepted.verdict == ClaimVerdict.INFERENCE
    assert next(
        check for check in rejected.checks if check.name == CheckName.INFERENCE_LABEL
    ).code == "INFERENCE_LABEL_MISSING"


def test_qualifier_strengthening_makes_claim_unsupported() -> None:
    span = EvidenceSpan(
        "qualified",
        SCAN_ID,
        "app/checkout.py",
        20,
        20,
        "PaymentService may retry checkout.",
    )
    claim = ClaimDraft(
        claim_id="claim-qualified",
        text="PaymentService must retry checkout.",
        importance=ClaimImportance.ESSENTIAL,
        citations=(Citation(SCAN_ID, "app/checkout.py", 20, 20),),
        entities=("PaymentService", "checkout"),
    )

    result = DeterministicClaimValidator(
        selected_scan_id=SCAN_ID,
        evidence_spans=(span,),
    ).validate(claim)

    assert result.verdict == ClaimVerdict.UNSUPPORTED
    qualifier_check = next(check for check in result.checks if check.name == CheckName.QUALIFIER)
    assert qualifier_check.code == "QUALIFIER_STRENGTHENED"


def test_citation_resolution_prefers_the_narrowest_overlapping_span() -> None:
    broad = EvidenceSpan(
        "module",
        SCAN_ID,
        "app/checkout.py",
        1,
        30,
        "module metadata without the cited entity",
    )
    narrow = EvidenceSpan(
        "function",
        SCAN_ID,
        "app/checkout.py",
        7,
        9,
        SPAN.text,
    )
    validator = DeterministicClaimValidator(
        selected_scan_id=SCAN_ID,
        evidence_spans=(broad, narrow),
        structural_evidence=(StructuralEvidence(SCAN_ID, ASSERTION, True, narrow.span_id),),
    )

    result = validator.validate(_claim())

    assert result.verdict == ClaimVerdict.SUPPORTED
    assert result.evidence_span_ids == ("function",)
