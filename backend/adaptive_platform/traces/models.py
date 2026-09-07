from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class TraceCategory(StrEnum):
    REPOSITORY = "REPOSITORY"
    RETRIEVAL = "RETRIEVAL"
    DECISION = "DECISION"
    EXECUTION = "EXECUTION"
    VERIFICATION = "VERIFICATION"
    MODEL_INTERACTION = "MODEL_INTERACTION"
    HUMAN_FEEDBACK = "HUMAN_FEEDBACK"
    LEARNING = "LEARNING"


class ActorType(StrEnum):
    SYSTEM = "SYSTEM"
    MODEL = "MODEL"
    HUMAN = "HUMAN"


@dataclass(frozen=True, slots=True)
class TraceEvent:
    task_id: str
    category: TraceCategory
    event_type: str
    actor_type: ActorType
    summary: str
    id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    schema_version: str = "1.0.0"
    repository_id: str | None = None
    scan_id: str | None = None
    correlation_id: str | None = None
    parent_event_id: str | None = None
    correction_of: str | None = None
    rationale_summary: str | None = None
    input_refs: tuple[str, ...] = ()
    output_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "repository_id": self.repository_id,
            "scan_id": self.scan_id,
            "correlation_id": self.correlation_id,
            "parent_event_id": self.parent_event_id,
            "correction_of": self.correction_of,
            "category": self.category.value,
            "event_type": self.event_type,
            "actor_type": self.actor_type.value,
            "occurred_at": self.occurred_at.isoformat(),
            "summary": self.summary,
            "rationale_summary": self.rationale_summary,
            "input_refs": list(self.input_refs),
            "output_refs": list(self.output_refs),
            "metadata": self.metadata,
        }

