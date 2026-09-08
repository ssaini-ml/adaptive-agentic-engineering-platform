from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from evaluation.check_review_complete import REQUIRED_BASELINES, check_release


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _valid_review() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "status": "COMPLETE",
        "counting_rules_version": "1.0.0",
        "reviewers": ["Ada Lovelace", "Grace Hopper"],
        "first_pass_agreement": 0.96,
        "adjudication_completed": True,
        "reviewed_fixtures": {
            "fx-small": "2.0.0",
            "fx-fastapi": "2.0.0",
            "fx-messy": "2.0.0",
            "fx-polyglot": "2.0.0",
        },
        "release_approval": {
            "status": "APPROVED",
            "approver": "Release Owner",
            "approved_at": "2026-09-08T10:00:00Z",
            "evidence_ref": "approval:release-1",
        },
    }


def _build_valid_evaluation_root(root: Path) -> None:
    fixture_counts = {
        "fx-small": 40,
        "fx-fastapi": 180,
        "fx-messy": 90,
        "fx-polyglot": 20,
    }
    for fixture_id in fixture_counts:
        fixture = root / "fixtures" / fixture_id
        _write_json(
            fixture / "manifest.json",
            {
                "fixture_id": fixture_id,
                "fixture_version": "2.0.0",
                "golden_file": "golden.json",
                "counting_rules_version": "1.0.0",
                "label_status": "APPROVED",
            },
        )
        _write_json(fixture / "golden.json", {"label_status": "APPROVED"})

    fixtures = [
        {"fixture_id": fixture_id, "file_count": file_count}
        for fixture_id, file_count in fixture_counts.items()
    ]
    for name in REQUIRED_BASELINES:
        payload: dict[str, object] = {
            "technical_status": "PASS",
            "human_label_review": "COMPLETE",
        }
        if name == "milestone0.json":
            payload["fixtures"] = fixtures
        _write_json(root / "baselines" / name, payload)

    _write_json(
        root / "holdout" / "manifest.json",
        {
            "fixture_id": "fx-python-holdout",
            "review_status": "APPROVED",
            "counting_rules_version": "1.0.0",
            "pinned_commit": "a" * 40,
            "content_fingerprint": "b" * 64,
            "file_count": 100,
            "license_status": "APPROVED",
            "provenance_status": "APPROVED",
        },
    )
    _write_json(
        root / "holdout" / "result.json",
        {
            "fixture_id": "fx-python-holdout",
            "technical_status": "PASS",
            "holdout_regression": "PASS",
            "evaluated_at": "2026-09-08T10:00:00Z",
            "evidence_ref": "holdout-run:release-1",
        },
    )


def test_complete_release_evidence_passes(tmp_path: Path) -> None:
    _build_valid_evaluation_root(tmp_path)

    assert check_release(_valid_review(), tmp_path) == []


def test_reviewers_must_be_distinct_and_agreement_must_be_bounded(tmp_path: Path) -> None:
    _build_valid_evaluation_root(tmp_path)
    review = deepcopy(_valid_review())
    review["reviewers"] = ["Ada Lovelace", " ada lovelace "]
    review["first_pass_agreement"] = 1.5

    errors = check_release(review, tmp_path)

    assert "reviewers must be distinct people" in errors
    assert "first_pass_agreement must be from 0.0 through 1.0" in errors


def test_release_rejects_stale_baseline_small_fixture_and_missing_holdout(
    tmp_path: Path,
) -> None:
    _build_valid_evaluation_root(tmp_path)
    milestone_zero = tmp_path / "baselines" / "milestone0.json"
    baseline = json.loads(milestone_zero.read_text(encoding="utf-8"))
    baseline["human_label_review"] = "PENDING_HUMAN_REVIEW"
    baseline["fixtures"][0]["file_count"] = 5
    _write_json(milestone_zero, baseline)
    (tmp_path / "holdout" / "result.json").unlink()

    errors = check_release(_valid_review(), tmp_path)

    assert "milestone0.json was not generated after completed human review" in errors
    assert "fx-small has 5 files; release minimum is 40" in errors
    assert "missing required file: result.json" in errors


def test_release_rejects_unapproved_fixture_and_placeholder_approval(tmp_path: Path) -> None:
    _build_valid_evaluation_root(tmp_path)
    fixture = tmp_path / "fixtures" / "fx-fastapi"
    manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
    manifest["label_status"] = "PROVISIONAL_HUMAN_REVIEW_REQUIRED"
    _write_json(fixture / "manifest.json", manifest)
    review = deepcopy(_valid_review())
    review["release_approval"]["approver"] = "TBD"  # type: ignore[index]

    errors = check_release(review, tmp_path)

    assert "fx-fastapi manifest labels are not APPROVED" in errors
    assert "release approval requires a named human approver" in errors
