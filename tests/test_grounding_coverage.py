from __future__ import annotations

from uuid import uuid4

import pytest
from adaptive_platform.grounding import (
    AnswerDecision,
    Citation,
    ClaimDraft,
    ClaimImportance,
    ClaimVerdict,
    ContextSlot,
    ContextSlotRequirement,
    CoverageResult,
    NamedGap,
    ValidatedClaim,
    decide_answer,
    evaluate_coverage,
)


def _validated(
    claim_id: str,
    importance: ClaimImportance,
    verdict: ClaimVerdict,
) -> ValidatedClaim:
    claim = ClaimDraft(
        claim_id=claim_id,
        text=f"claim {claim_id}",
        importance=importance,
        citations=(Citation(uuid4(), "app.py", 1, 1),),
        entities=(claim_id,),
    )
    gaps = (
        ()
        if verdict in {ClaimVerdict.SUPPORTED, ClaimVerdict.INFERENCE}
        else (NamedGap(f"claim:{claim_id}:support", "CLAIM_UNSUPPORTED", claim_id),)
    )
    return ValidatedClaim(claim, verdict, ("span",), (), gaps)


def test_coverage_gate_answers_only_when_all_slots_are_filled() -> None:
    requirements = (
        ContextSlotRequirement("target_symbol"),
        ContextSlotRequirement("incoming_edges"),
    )
    result = evaluate_coverage(
        requirements,
        (ContextSlot("target_symbol", ("symbol-1",)), ContextSlot("incoming_edges", ("edge-1",))),
    )

    assert result.decision == AnswerDecision.ANSWERED
    assert result.filled_slots == ("target_symbol", "incoming_edges")
    assert result.gaps == ()


def test_missing_essential_slot_abstains_and_names_the_gap() -> None:
    result = evaluate_coverage(
        (ContextSlotRequirement("target_symbol"), ContextSlotRequirement("incoming_edges")),
        (ContextSlot("target_symbol", ("symbol-1",)),),
    )

    assert result.decision == AnswerDecision.ABSTAIN
    assert [(gap.name, gap.code) for gap in result.gaps] == [
        ("incoming_edges", "MISSING_ESSENTIAL_SLOT")
    ]


def test_missing_optional_slot_produces_partial_coverage() -> None:
    result = evaluate_coverage(
        (
            ContextSlotRequirement("target_symbol"),
            ContextSlotRequirement("documentation", essential=False),
        ),
        (ContextSlot("target_symbol", ("symbol-1",)),),
    )

    assert result.decision == AnswerDecision.PARTIAL
    assert result.gaps[0].name == "documentation"


def test_coverage_rejects_ambiguous_duplicate_slot_names() -> None:
    with pytest.raises(ValueError, match="Context slot names must be unique"):
        evaluate_coverage(
            (ContextSlotRequirement("target"), ContextSlotRequirement("target")),
            (),
        )


def test_unsupported_optional_claim_is_removed_and_reported_as_partial() -> None:
    coverage = CoverageResult(AnswerDecision.ANSWERED, ("target",), ())
    essential = _validated("essential", ClaimImportance.ESSENTIAL, ClaimVerdict.SUPPORTED)
    optional = _validated("optional", ClaimImportance.OPTIONAL, ClaimVerdict.UNSUPPORTED)

    result = decide_answer(coverage, (essential, optional))

    assert result.decision == AnswerDecision.PARTIAL
    assert result.claims == (essential,)
    assert result.gaps[0].claim_id == "optional"


def test_unsupported_essential_claim_forces_abstention_without_answer_claims() -> None:
    coverage = CoverageResult(AnswerDecision.ANSWERED, ("target",), ())
    essential = _validated("essential", ClaimImportance.ESSENTIAL, ClaimVerdict.CONFLICTING)
    optional = _validated("optional", ClaimImportance.OPTIONAL, ClaimVerdict.SUPPORTED)

    result = decide_answer(coverage, (essential, optional))

    assert result.decision == AnswerDecision.ABSTAIN
    assert result.claims == ()
    assert result.gaps[0].claim_id == "essential"


def test_pre_generation_coverage_abstention_takes_precedence() -> None:
    coverage = CoverageResult(
        AnswerDecision.ABSTAIN,
        (),
        (NamedGap("incoming_edges", "MISSING_ESSENTIAL_SLOT"),),
    )
    supported = _validated("claim", ClaimImportance.ESSENTIAL, ClaimVerdict.SUPPORTED)

    result = decide_answer(coverage, (supported,))

    assert result.decision == AnswerDecision.ABSTAIN
    assert result.claims == ()
    assert result.gaps == coverage.gaps
