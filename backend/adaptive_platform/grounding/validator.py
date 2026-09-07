from __future__ import annotations

from uuid import UUID

from adaptive_platform.grounding.citations import CitationValidationInput, resolve_citation
from adaptive_platform.grounding.models import (
    CheckName,
    CheckStatus,
    ClaimDraft,
    ClaimVerdict,
    EvidenceSpan,
    NamedGap,
    StructuralEvidence,
    ValidatedClaim,
    ValidationCheck,
)
from adaptive_platform.grounding.support import (
    LexicalSupportInput,
    QualifierPreservationInput,
    StructuralSupportInput,
    check_lexical_support,
    check_qualifier_preservation,
    check_structural_support,
)


class DeterministicClaimValidator:
    def __init__(
        self,
        *,
        selected_scan_id: UUID,
        evidence_spans: tuple[EvidenceSpan, ...],
        structural_evidence: tuple[StructuralEvidence, ...] = (),
    ) -> None:
        self._selected_scan_id = selected_scan_id
        self._evidence_spans = evidence_spans
        self._structural_evidence = structural_evidence

    def validate(self, claim: ClaimDraft) -> ValidatedClaim:
        checks: list[ValidationCheck] = []
        gaps: list[NamedGap] = []
        resolved: list[EvidenceSpan] = []

        if not claim.citations:
            checks.append(
                ValidationCheck(CheckName.CITATION, CheckStatus.FAIL, "CITATION_REQUIRED")
            )
            gaps.append(_claim_gap(claim, "citation", "CITATION_REQUIRED"))
        else:
            citation_failures: list[str] = []
            for citation in claim.citations:
                resolution = resolve_citation(
                    CitationValidationInput(citation, self._selected_scan_id, self._evidence_spans)
                )
                if resolution.valid and resolution.evidence_span is not None:
                    resolved.append(resolution.evidence_span)
                else:
                    citation_failures.append(resolution.code)
            if citation_failures:
                code = min(citation_failures)
                checks.append(ValidationCheck(CheckName.CITATION, CheckStatus.FAIL, code))
                gaps.append(_claim_gap(claim, "citation", code))
            else:
                checks.append(
                    ValidationCheck(
                        CheckName.CITATION,
                        CheckStatus.PASS,
                        "CITATIONS_RESOLVED",
                        _span_ids(resolved),
                    )
                )

        structural_conflict = False
        if claim.structural_assertion is None:
            checks.append(
                ValidationCheck(
                    CheckName.STRUCTURAL,
                    CheckStatus.SKIPPED,
                    "NO_STRUCTURAL_ASSERTION",
                )
            )
        else:
            structural = check_structural_support(
                StructuralSupportInput(
                    claim.structural_assertion,
                    self._selected_scan_id,
                    self._structural_evidence,
                )
            )
            structural_conflict = structural.conflicting
            status = CheckStatus.PASS if structural.supported else CheckStatus.FAIL
            checks.append(
                ValidationCheck(
                    CheckName.STRUCTURAL,
                    status,
                    structural.code,
                    structural.evidence_span_ids,
                )
            )
            if not structural.supported:
                gaps.append(_claim_gap(claim, "structure", structural.code))

        lexical = check_lexical_support(LexicalSupportInput(claim.entities, tuple(resolved)))
        checks.append(
            ValidationCheck(
                CheckName.LEXICAL,
                CheckStatus.PASS if lexical.supported else CheckStatus.FAIL,
                lexical.code,
                _span_ids(resolved),
            )
        )
        if not lexical.supported:
            gaps.append(_claim_gap(claim, "lexical-support", lexical.code))

        qualifiers = check_qualifier_preservation(
            QualifierPreservationInput(claim.text, tuple(resolved))
        )
        checks.append(
            ValidationCheck(
                CheckName.QUALIFIER,
                CheckStatus.PASS if qualifiers.preserved else CheckStatus.FAIL,
                qualifiers.code,
                _span_ids(resolved),
            )
        )
        if not qualifiers.preserved:
            gaps.append(_claim_gap(claim, "qualifier", qualifiers.code))

        inference_label_valid = (
            claim.requested_verdict != ClaimVerdict.INFERENCE or claim.inference_labeled_inline
        )
        checks.append(
            ValidationCheck(
                CheckName.INFERENCE_LABEL,
                CheckStatus.PASS if inference_label_valid else CheckStatus.FAIL,
                "INFERENCE_LABEL_VALID" if inference_label_valid else "INFERENCE_LABEL_MISSING",
            )
        )
        if not inference_label_valid:
            gaps.append(_claim_gap(claim, "inference-label", "INFERENCE_LABEL_MISSING"))

        if structural_conflict:
            verdict = ClaimVerdict.CONFLICTING
        elif any(check.status == CheckStatus.FAIL for check in checks):
            verdict = ClaimVerdict.UNSUPPORTED
        else:
            verdict = claim.requested_verdict
        return ValidatedClaim(
            claim=claim,
            verdict=verdict,
            evidence_span_ids=_span_ids(resolved),
            checks=tuple(checks),
            gaps=tuple(gaps),
        )


def _claim_gap(claim: ClaimDraft, suffix: str, code: str) -> NamedGap:
    return NamedGap(name=f"claim:{claim.claim_id}:{suffix}", code=code, claim_id=claim.claim_id)


def _span_ids(spans: list[EvidenceSpan]) -> tuple[str, ...]:
    return tuple(sorted({span.span_id for span in spans}))
