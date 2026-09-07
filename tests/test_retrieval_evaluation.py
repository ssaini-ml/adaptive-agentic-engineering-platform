from pathlib import Path

from adaptive_platform.retrieval.evaluation import build_report

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_milestone_3ab_retrieval_gates_pass() -> None:
    report = build_report(PROJECT_ROOT)

    assert report["technical_status"] == "PASS"
    assert report["human_label_review"] == "PENDING_HUMAN_REVIEW"
    assert report["full_text_status"] == "DEFERRED_TO_M3C"
    assert len(report["exact_cases"]) == 3
    assert len(report["graph_cases"]) == 4
    assert all(item["status"] == "PASS" for item in report["gates"])
