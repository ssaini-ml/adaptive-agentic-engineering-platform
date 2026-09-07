from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from adaptive_platform.traces.models import TraceEvent


class TraceValidationError(ValueError):
    pass


class JsonlTraceRecorder:
    """Development recorder; PostgreSQL becomes authoritative in Milestone 1."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()

    def append(self, event: TraceEvent) -> None:
        payload = event.to_dict()
        _validate_payload(payload)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(encoded + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise TraceValidationError(
                    f"Invalid trace JSON at {self.path}:{line_number}"
                ) from exc
            _validate_payload(payload)
            events.append(payload)
        return events


def _validate_payload(payload: dict[str, Any]) -> None:
    required = {
        "id",
        "schema_version",
        "task_id",
        "category",
        "event_type",
        "actor_type",
        "occurred_at",
        "summary",
        "metadata",
    }
    missing = required - payload.keys()
    if missing:
        raise TraceValidationError(f"Trace event is missing fields: {sorted(missing)}")
    if not payload["summary"]:
        raise TraceValidationError("Trace summary must not be empty")
    if "chain_of_thought" in payload or "hidden_reasoning" in payload:
        raise TraceValidationError("Hidden reasoning must never be stored")
