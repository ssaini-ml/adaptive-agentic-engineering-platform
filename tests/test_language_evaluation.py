from __future__ import annotations

from pathlib import Path

from adaptive_platform.languages.evaluation import (
    build_language_report,
    evaluate_fixture_language_profile,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_ROOT = PROJECT_ROOT / "evaluation"


def test_polyglot_fixture_reports_minority_and_unsupported_languages() -> None:
    result = evaluate_fixture_language_profile(EVALUATION_ROOT / "fixtures" / "fx-polyglot")

    assert result["actual"]["repository_type"] == "POLYGLOT"
    assert result["actual"]["primary_language"] == "TypeScript"
    assert result["actual"]["extractor_status"] == {
        "Go": "UNSUPPORTED",
        "Python": "SUPPORTED",
        "TypeScript": "UNSUPPORTED",
    }
    assert result["language_files"]["precision"] == 1.0
    assert result["language_files"]["recall"] == 1.0
    assert result["unsupported_reporting"]["recall"] == 1.0


def test_milestone_2a_language_gates_pass_without_claiming_human_review() -> None:
    report = build_language_report(EVALUATION_ROOT)

    assert report["technical_status"] == "PASS"
    assert report["human_label_review"] == "PENDING_HUMAN_REVIEW"
    assert all(gate["passed"] for gate in report["gates"].values())
