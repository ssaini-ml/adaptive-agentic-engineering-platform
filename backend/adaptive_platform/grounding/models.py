from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ClaimImportance(StrEnum):
    ESSENTIAL = "ESSENTIAL"
    OPTIONAL = "OPTIONAL"


class ClaimVerdict(StrEnum):
    SUPPORTED = "SUPPORTED"
    INFERENCE = "INFERENCE"
    UNSUPPORTED = "UNSUPPORTED"
    CONFLICTING = "CONFLICTING"


class AnswerDecision(StrEnum):
    ANSWERED = "ANSWERED"
    PARTIAL = "PARTIAL"
    ABSTAIN = "ABSTAIN"


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class CheckName(StrEnum):
    CITATION = "CITATION"
    STRUCTURAL = "STRUCTURAL"
    LEXICAL = "LEXICAL"
    QUALIFIER = "QUALIFIER"
    INFERENCE_LABEL = "INFERENCE_LABEL"


@dataclass(frozen=True, slots=True)
class Citation:
    scan_id: UUID
    path: str
    start_line: int
    end_line: int
    start_column: int = 0
    end_column: int | None = None
    evidence_span_id: str | None = None

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("Citation path cannot be empty")
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("Citation lines must form a positive ordered range")
        if self.start_column < 0:
            raise ValueError("Citation start_column cannot be negative")
        if self.end_column is not None and self.end_column < 0:
            raise ValueError("Citation end_column cannot be negative")
        if (
            self.start_line == self.end_line
            and self.end_column is not None
            and self.end_column < self.start_column
        ):
            raise ValueError("Citation columns must form an ordered range")


@dataclass(frozen=True, slots=True)
class EvidenceSpan:
    span_id: str
    scan_id: UUID
    path: str
    start_line: int
    end_line: int
    text: str
    start_column: int = 0
    end_column: int | None = None

    def __post_init__(self) -> None:
        if not self.span_id or not self.path:
            raise ValueError("Evidence span identity and path cannot be empty")
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("Evidence span lines must form a positive ordered range")
        if self.start_column < 0:
            raise ValueError("Evidence span start_column cannot be negative")
        if self.end_column is not None and self.end_column < 0:
            raise ValueError("Evidence span end_column cannot be negative")


@dataclass(frozen=True, slots=True)
class StructuralAssertion:
    source: str
    relationship_type: str
    target: str

    def __post_init__(self) -> None:
        if not self.source or not self.relationship_type or not self.target:
            raise ValueError("Structural assertions require a source, relationship and target")


@dataclass(frozen=True, slots=True)
class StructuralEvidence:
    scan_id: UUID
    assertion: StructuralAssertion
    supports: bool
    evidence_span_id: str | None = None


@dataclass(frozen=True, slots=True)
class ClaimDraft:
    claim_id: str
    text: str
    importance: ClaimImportance
    citations: tuple[Citation, ...]
    entities: tuple[str, ...]
    structural_assertion: StructuralAssertion | None = None
    requested_verdict: ClaimVerdict = ClaimVerdict.SUPPORTED
    inference_labeled_inline: bool = False

    def __post_init__(self) -> None:
        if not self.claim_id or not self.text:
            raise ValueError("Claims require a stable id and non-empty text")
        if self.requested_verdict not in {ClaimVerdict.SUPPORTED, ClaimVerdict.INFERENCE}:
            raise ValueError("A draft may request only SUPPORTED or INFERENCE")


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    name: CheckName
    status: CheckStatus
    code: str
    evidence_span_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NamedGap:
    name: str
    code: str
    claim_id: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedClaim:
    claim: ClaimDraft
    verdict: ClaimVerdict
    evidence_span_ids: tuple[str, ...]
    checks: tuple[ValidationCheck, ...]
    gaps: tuple[NamedGap, ...]


@dataclass(frozen=True, slots=True)
class ContextSlotRequirement:
    name: str
    essential: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Context slot names cannot be empty")


@dataclass(frozen=True, slots=True)
class ContextSlot:
    name: str
    evidence_refs: tuple[str, ...] = ()

    @property
    def filled(self) -> bool:
        return bool(self.evidence_refs)


@dataclass(frozen=True, slots=True)
class CoverageResult:
    decision: AnswerDecision
    filled_slots: tuple[str, ...]
    gaps: tuple[NamedGap, ...]


@dataclass(frozen=True, slots=True)
class GroundingDecision:
    decision: AnswerDecision
    claims: tuple[ValidatedClaim, ...]
    gaps: tuple[NamedGap, ...]
