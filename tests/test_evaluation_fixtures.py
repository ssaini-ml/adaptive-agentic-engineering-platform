from __future__ import annotations

import json
import unittest
from pathlib import Path

from adaptive_platform.evaluation.loader import discover_fixture_dirs, validate_fixture
from adaptive_platform.evaluation.runner import build_report, evaluate_predictions

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_ROOT = PROJECT_ROOT / "evaluation"


class FixtureTests(unittest.TestCase):
    def test_all_development_fixtures_are_valid_and_pinned(self) -> None:
        fixture_dirs = discover_fixture_dirs(EVALUATION_ROOT / "fixtures")
        summaries = [validate_fixture(fixture_dir) for fixture_dir in fixture_dirs]
        self.assertEqual(
            [summary.fixture_id for summary in summaries],
            ["fx-fastapi", "fx-messy", "fx-polyglot", "fx-small"],
        )
        self.assertEqual(summaries[2].languages, ("Python", "TypeScript", "Go"))
        self.assertEqual(summaries[2].evaluator_profile, "language-profile-v1")
        self.assertTrue(
            all(
                summary.languages == ("Python",)
                for index, summary in enumerate(summaries)
                if index != 2
            )
        )
        self.assertTrue(all(summary.pinned_revision == "synthetic-v1.0.0" for summary in summaries))
        self.assertTrue(all(len(summary.content_fingerprint) == 64 for summary in summaries))
        self.assertGreaterEqual(sum(summary.language_file_labels for summary in summaries), 28)
        self.assertGreaterEqual(sum(summary.question_labels for summary in summaries), 9)
        self.assertGreaterEqual(sum(summary.unanswerable_questions for summary in summaries), 3)

    def test_golden_predictions_score_perfectly(self) -> None:
        fixture = EVALUATION_ROOT / "fixtures" / "fx-fastapi"
        golden = json.loads((fixture / "golden.json").read_text())
        scores = evaluate_predictions(golden, golden)
        for kind in ("symbols", "imports", "routes"):
            self.assertEqual(scores[kind]["precision"], 1.0)
            self.assertEqual(scores[kind]["recall"], 1.0)

    def test_milestone_zero_report_is_honest_about_human_review(self) -> None:
        report = build_report(EVALUATION_ROOT)
        self.assertEqual(report["technical_status"], "PASS")
        self.assertEqual(report["human_label_review"], "PENDING_HUMAN_REVIEW")
        self.assertEqual(report["v0_1_release_gates"]["status"], "NOT_RUN")
        self.assertEqual(report["holdout"]["status"], "POLICY_DEFINED_SELECTION_PENDING")


if __name__ == "__main__":
    unittest.main()
