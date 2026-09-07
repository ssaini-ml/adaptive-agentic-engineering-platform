from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from adaptive_platform.grounding.models import EvidenceSpan, StructuralAssertion, StructuralEvidence

_IDENTIFIER_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_WORD = re.compile(r"[^A-Za-z0-9]+")


@dataclass(frozen=True, slots=True)
class LexicalSupportInput:
    entities: tuple[str, ...]
    evidence_spans: tuple[EvidenceSpan, ...]


@dataclass(frozen=True, slots=True)
class LexicalSupportResult:
    supported: bool
    code: str
    missing_entities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StructuralSupportInput:
    assertion: StructuralAssertion
    selected_scan_id: UUID
    evidence: tuple[StructuralEvidence, ...]


@dataclass(frozen=True, slots=True)
class StructuralSupportResult:
    supported: bool
    conflicting: bool
    code: str
    evidence_span_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QualifierPreservationInput:
    claim_text: str
    evidence_spans: tuple[EvidenceSpan, ...]


@dataclass(frozen=True, slots=True)
class QualifierViolation:
    source_qualifier: str
    claim_qualifier: str


@dataclass(frozen=True, slots=True)
class QualifierPreservationResult:
    preserved: bool
    code: str
    violations: tuple[QualifierViolation, ...] = ()


def check_lexical_support(value: LexicalSupportInput) -> LexicalSupportResult:
    if not value.entities:
        return LexicalSupportResult(supported=False, code="LEXICAL_ENTITIES_REQUIRED")

    evidence_tokens = tuple(
        token for span in value.evidence_spans for token in _identifier_tokens(span.text)
    )
    missing = tuple(
        entity
        for entity in value.entities
        if not _contains_token_sequence(evidence_tokens, _identifier_tokens(entity))
    )
    if missing:
        return LexicalSupportResult(
            supported=False,
            code="LEXICAL_ENTITY_MISSING",
            missing_entities=missing,
        )
    return LexicalSupportResult(supported=True, code="LEXICAL_ENTITIES_PRESENT")


def check_structural_support(value: StructuralSupportInput) -> StructuralSupportResult:
    matches = tuple(
        item
        for item in value.evidence
        if item.scan_id == value.selected_scan_id and item.assertion == value.assertion
    )
    evidence_ids = tuple(
        sorted({item.evidence_span_id for item in matches if item.evidence_span_id is not None})
    )
    if any(not item.supports for item in matches):
        return StructuralSupportResult(
            supported=False,
            conflicting=True,
            code="STRUCTURAL_EVIDENCE_CONFLICT",
            evidence_span_ids=evidence_ids,
        )
    if any(item.supports for item in matches):
        return StructuralSupportResult(
            supported=True,
            conflicting=False,
            code="STRUCTURAL_EDGE_PRESENT",
            evidence_span_ids=evidence_ids,
        )
    return StructuralSupportResult(
        supported=False,
        conflicting=False,
        code="STRUCTURAL_EDGE_MISSING",
    )


def check_qualifier_preservation(
    value: QualifierPreservationInput,
) -> QualifierPreservationResult:
    source = " ".join(span.text.lower() for span in value.evidence_spans)
    claim = value.claim_text.lower()
    violations: list[QualifierViolation] = []

    transformations = (
        (("may", "might", "could"), ("must", "will")),
        (("usually", "often", "sometimes", "occasionally"), ("always",)),
        (("some",), ("all", "every")),
        (("in most cases", "most"), ("always", "all", "every")),
        (("appears to", "seems to"), (" is ", "are ")),
        (("likely", "probably"), ("certain", "certainly", "definitely", "guaranteed")),
    )
    padded_claim = f" {claim} "
    padded_source = f" {source} "
    for weaker_terms, stronger_terms in transformations:
        weaker = next((term for term in weaker_terms if _has_phrase(padded_source, term)), None)
        stronger = next((term for term in stronger_terms if _has_phrase(padded_claim, term)), None)
        if weaker is not None and stronger is not None:
            violations.append(QualifierViolation(weaker, stronger.strip()))

    if violations:
        return QualifierPreservationResult(
            preserved=False,
            code="QUALIFIER_STRENGTHENED",
            violations=tuple(violations),
        )
    return QualifierPreservationResult(preserved=True, code="QUALIFIERS_PRESERVED")


def _identifier_tokens(value: str) -> tuple[str, ...]:
    separated = _IDENTIFIER_BOUNDARY.sub(" ", value)
    return tuple(part.lower() for part in _NON_WORD.split(separated) if part)


def _contains_token_sequence(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    if not needle:
        return False
    size = len(needle)
    return any(haystack[index : index + size] == needle for index in range(len(haystack) - size + 1))


def _has_phrase(padded_text: str, phrase: str) -> bool:
    pattern = r"(?<![A-Za-z0-9])" + re.escape(phrase.strip()) + r"(?![A-Za-z0-9])"
    return re.search(pattern, padded_text) is not None
