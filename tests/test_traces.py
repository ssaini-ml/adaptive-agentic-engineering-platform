from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adaptive_platform.traces import (
    ActorType,
    JsonlTraceRecorder,
    TraceCategory,
    TraceEvent,
    TraceValidationError,
)


class TraceTests(unittest.TestCase):
    def test_round_trip_preserves_linked_correction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            recorder = JsonlTraceRecorder(Path(directory) / "trace.jsonl")
            decision = TraceEvent(
                task_id="task-1",
                category=TraceCategory.DECISION,
                event_type="retrieval_strategy_selected",
                actor_type=ActorType.MODEL,
                summary="Selected graph retrieval.",
                rationale_summary="The classified question asks for dependencies.",
            )
            correction = TraceEvent(
                task_id="task-1",
                category=TraceCategory.HUMAN_FEEDBACK,
                event_type="decision_corrected",
                actor_type=ActorType.HUMAN,
                summary="Evaluation must cover non-Python repositories.",
                correction_of=str(decision.id),
            )

            recorder.append(decision)
            recorder.append(correction)
            events = recorder.read_all()

            self.assertEqual(len(events), 2)
            self.assertEqual(events[1]["correction_of"], events[0]["id"])
            self.assertEqual(events[1]["category"], "HUMAN_FEEDBACK")

    def test_hidden_reasoning_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            payload = TraceEvent(
                task_id="task-1",
                category=TraceCategory.DECISION,
                event_type="example",
                actor_type=ActorType.SYSTEM,
                summary="Observable decision.",
            ).to_dict()
            payload["chain_of_thought"] = "must not be stored"
            path.write_text(json.dumps(payload) + "\n")

            with self.assertRaisesRegex(TraceValidationError, "Hidden reasoning"):
                JsonlTraceRecorder(path).read_all()


if __name__ == "__main__":
    unittest.main()

