from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Score:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FixtureSummary:
    fixture_id: str
    fixture_version: str
    languages: tuple[str, ...]
    evaluator_profile: str
    pinned_revision: str
    content_fingerprint: str
    file_count: int
    language_file_labels: int
    symbol_labels: int
    import_labels: int
    route_labels: int
    question_labels: int
    answerable_questions: int
    unanswerable_questions: int
    label_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
