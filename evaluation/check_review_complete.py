"""Validate all recorded evidence required before a V0.1 release is published.

The release workflow intentionally fails throughout ordinary development. Passing
requires completed independent review, frozen release-scale fixtures, green
technical baselines, a reviewed holdout result, and named final approval.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

EVALUATION_ROOT = Path(__file__).parent
REVIEW_PATH = EVALUATION_ROOT / "review.json"
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_COUNTING_RULES_VERSION = "1.0.0"
PLACEHOLDER_NAMES = {
    "",
    "tbd",
    "todo",
    "n/a",
    "reviewer a",
    "reviewer b",
    "agent",
    "claude",
    "codex",
    "chatgpt",
    "ai",
}
REQUIRED_BASELINES = (
    "milestone0.json",
    "milestone2a.json",
    "milestone2b.json",
    "milestone3ab.json",
    "milestone3c.json",
    "milestone4.json",
)
RELEASE_FIXTURE_MINIMUM_FILES = {
    "fx-small": 40,
    "fx-fastapi": 180,
    "fx-messy": 90,
}
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")


def load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing required file: {path.name}")
        return None
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read {path.name}: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{path.name} must contain a JSON object")
        return None
    return value


def _real_name(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower() not in PLACEHOLDER_NAMES


def check_review(data: dict[str, Any], evaluation_root: Path) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        errors.append(f"review schema_version must be {EXPECTED_SCHEMA_VERSION!r}")
    if data.get("status") != "COMPLETE":
        errors.append(f"status is {data.get('status')!r}, expected 'COMPLETE'")
    if data.get("counting_rules_version") != EXPECTED_COUNTING_RULES_VERSION:
        errors.append("review counting_rules_version does not match the release gate version")

    reviewers = data.get("reviewers")
    if not isinstance(reviewers, list):
        errors.append("reviewers must be a list")
        reviewers = []
    if len(reviewers) < 2:
        errors.append(f"expected at least 2 reviewers, found {len(reviewers)}")
    normalized_reviewers = [str(item).strip().casefold() for item in reviewers]
    if len(normalized_reviewers) != len(set(normalized_reviewers)):
        errors.append("reviewers must be distinct people")
    for reviewer in reviewers:
        if not _real_name(reviewer):
            errors.append(f"reviewer name {reviewer!r} is empty or a placeholder")

    agreement = data.get("first_pass_agreement")
    if isinstance(agreement, bool) or not isinstance(agreement, (int, float)):
        errors.append("first_pass_agreement must be a number from 0.0 through 1.0")
    elif not 0.0 <= agreement <= 1.0:
        errors.append("first_pass_agreement must be from 0.0 through 1.0")
    if data.get("adjudication_completed") is not True:
        errors.append("adjudication_completed is not true")

    reviewed_fixtures = data.get("reviewed_fixtures")
    if not isinstance(reviewed_fixtures, dict):
        errors.append("reviewed_fixtures must map fixture IDs to reviewed versions")
        reviewed_fixtures = {}
    fixture_root = evaluation_root / "fixtures"
    if fixture_root.is_dir():
        for fixture_dir in sorted(path for path in fixture_root.iterdir() if path.is_dir()):
            manifest = load_json(fixture_dir / "manifest.json", errors)
            if manifest is None:
                continue
            fixture_id = manifest.get("fixture_id")
            if not isinstance(fixture_id, str):
                errors.append(f"{fixture_dir.name} manifest lacks a fixture_id")
                continue
            expected_version = manifest.get("fixture_version")
            if reviewed_fixtures.get(fixture_id) != expected_version:
                errors.append(
                    f"{fixture_id} version {expected_version!r} lacks matching review evidence"
                )
            if manifest.get("counting_rules_version") != EXPECTED_COUNTING_RULES_VERSION:
                errors.append(f"{fixture_id} uses an unexpected counting-rules version")
            if manifest.get("label_status") != "APPROVED":
                errors.append(f"{fixture_id} manifest labels are not APPROVED")
            golden = load_json(fixture_dir / manifest.get("golden_file", "golden.json"), errors)
            if golden is not None and golden.get("label_status") != "APPROVED":
                errors.append(f"{fixture_id} golden labels are not APPROVED")
    else:
        errors.append("fixtures directory is missing")

    approval = data.get("release_approval")
    if not isinstance(approval, dict) or approval.get("status") != "APPROVED":
        errors.append("release_approval.status is not APPROVED")
    else:
        if not _real_name(approval.get("approver")):
            errors.append("release approval requires a named human approver")
        for field in ("approved_at", "evidence_ref"):
            if not isinstance(approval.get(field), str) or not approval[field].strip():
                errors.append(f"release approval requires {field}")
    return errors


def check_technical_evidence(evaluation_root: Path) -> list[str]:
    errors: list[str] = []
    baselines: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_BASELINES:
        baseline = load_json(evaluation_root / "baselines" / name, errors)
        if baseline is None:
            continue
        baselines[name] = baseline
        if baseline.get("technical_status") != "PASS":
            errors.append(f"{name} technical_status is not PASS")
        if baseline.get("human_label_review") != "COMPLETE":
            errors.append(f"{name} was not generated after completed human review")

    milestone_zero = baselines.get("milestone0.json")
    if milestone_zero is not None:
        fixtures = milestone_zero.get("fixtures")
        by_id = (
            {
                item.get("fixture_id"): item
                for item in fixtures
                if isinstance(item, dict) and isinstance(item.get("fixture_id"), str)
            }
            if isinstance(fixtures, list)
            else {}
        )
        for fixture_id, minimum in RELEASE_FIXTURE_MINIMUM_FILES.items():
            actual = by_id.get(fixture_id, {}).get("file_count")
            if not isinstance(actual, int) or actual < minimum:
                errors.append(f"{fixture_id} has {actual!r} files; release minimum is {minimum}")
    return errors


def check_holdout(evaluation_root: Path) -> list[str]:
    errors: list[str] = []
    manifest = load_json(evaluation_root / "holdout" / "manifest.json", errors)
    result = load_json(evaluation_root / "holdout" / "result.json", errors)
    if manifest is None or result is None:
        return errors

    fixture_id = manifest.get("fixture_id")
    if (
        not isinstance(fixture_id, str)
        or not fixture_id.startswith("fx-")
        or not fixture_id.endswith("-holdout")
    ):
        errors.append("holdout fixture_id must match fx-*-holdout")
    if manifest.get("review_status") != "APPROVED":
        errors.append("holdout manifest review_status is not APPROVED")
    if manifest.get("counting_rules_version") != EXPECTED_COUNTING_RULES_VERSION:
        errors.append("holdout counting-rules version does not match the release gate")
    if not _SHA40.fullmatch(str(manifest.get("pinned_commit", ""))):
        errors.append("holdout pinned_commit must be a 40-character lowercase SHA")
    if not _SHA64.fullmatch(str(manifest.get("content_fingerprint", ""))):
        errors.append("holdout content_fingerprint must be a 64-character lowercase SHA-256")
    file_count = manifest.get("file_count")
    if not isinstance(file_count, int) or not 75 <= file_count <= 250:
        errors.append("holdout file_count must be between 75 and 250")
    if manifest.get("license_status") != "APPROVED":
        errors.append("holdout license_status is not APPROVED")
    if manifest.get("provenance_status") != "APPROVED":
        errors.append("holdout provenance_status is not APPROVED")

    if result.get("fixture_id") != fixture_id:
        errors.append("holdout result fixture_id does not match its manifest")
    if result.get("technical_status") != "PASS":
        errors.append("holdout technical_status is not PASS")
    if result.get("holdout_regression") != "PASS":
        errors.append("holdout_regression is not PASS")
    for field in ("evaluated_at", "evidence_ref"):
        if not isinstance(result.get(field), str) or not result[field].strip():
            errors.append(f"holdout result requires {field}")
    return errors


def check_release(data: dict[str, Any], evaluation_root: Path = EVALUATION_ROOT) -> list[str]:
    return [
        *check_review(data, evaluation_root),
        *check_technical_evidence(evaluation_root),
        *check_holdout(evaluation_root),
    ]


def main() -> int:
    load_errors: list[str] = []
    data = load_json(REVIEW_PATH, load_errors)
    errors = load_errors if data is None else [*load_errors, *check_release(data)]
    if errors:
        print("V0.1 release evidence is incomplete:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("All recorded V0.1 technical, corpus, holdout, review, and approval gates pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
