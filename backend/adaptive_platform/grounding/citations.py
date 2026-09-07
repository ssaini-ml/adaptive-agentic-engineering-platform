from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from adaptive_platform.grounding.models import Citation, EvidenceSpan


@dataclass(frozen=True, slots=True)
class CitationValidationInput:
    citation: Citation
    selected_scan_id: UUID
    available_spans: tuple[EvidenceSpan, ...]


@dataclass(frozen=True, slots=True)
class CitationResolution:
    valid: bool
    code: str
    evidence_span: EvidenceSpan | None = None


def resolve_citation(value: CitationValidationInput) -> CitationResolution:
    citation = value.citation
    if citation.scan_id != value.selected_scan_id:
        return CitationResolution(valid=False, code="CITATION_SCAN_MISMATCH")

    candidates = sorted(
        (
            span
            for span in value.available_spans
            if span.scan_id == value.selected_scan_id
            and span.path == citation.path
            and (
                citation.evidence_span_id is None
                or span.span_id == citation.evidence_span_id
            )
        ),
        key=lambda span: (
            span.end_line - span.start_line,
            span.start_line,
            span.end_line,
            span.span_id,
        ),
    )
    for span in candidates:
        if not _contains(span, citation):
            continue
        return CitationResolution(valid=True, code="CITATION_RESOLVED", evidence_span=span)
    return CitationResolution(valid=False, code="CITATION_SPAN_NOT_FOUND")


def _contains(span: EvidenceSpan, citation: Citation) -> bool:
    if citation.start_line < span.start_line or citation.end_line > span.end_line:
        return False
    if citation.start_line == span.start_line and citation.start_column < span.start_column:
        return False
    return not (
        citation.end_line == span.end_line
        and citation.end_column is not None
        and span.end_column is not None
        and citation.end_column > span.end_column
    )
