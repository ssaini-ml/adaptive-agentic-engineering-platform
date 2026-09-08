"""Fail if evaluation/review.json does not show a completed independent human review.

Intended for the release-tag workflow only. review.json is expected to stay
incomplete throughout ordinary development, so this must never run as a normal
PR gate.
"""

import json
import sys
from pathlib import Path

REVIEW_PATH = Path(__file__).parent / "review.json"
PLACEHOLDER_NAMES = {"", "tbd", "todo", "n/a", "reviewer a", "reviewer b", "agent", "claude", "ai"}


def check(data: dict) -> list[str]:
    errors = []

    if data.get("status") != "COMPLETE":
        errors.append(f"status is {data.get('status')!r}, expected 'COMPLETE'")

    reviewers = data.get("reviewers", [])
    if len(reviewers) < 2:
        errors.append(f"expected at least 2 reviewers, found {len(reviewers)}")
    for reviewer in reviewers:
        if str(reviewer).strip().lower() in PLACEHOLDER_NAMES:
            errors.append(f"reviewer name {reviewer!r} looks like a placeholder, not a real reviewer")

    if not data.get("adjudication_completed"):
        errors.append("adjudication_completed is not true")

    if data.get("first_pass_agreement") in (None, ""):
        errors.append("first_pass_agreement is missing")

    return errors


def main() -> int:
    data = json.loads(REVIEW_PATH.read_text())
    errors = check(data)

    if errors:
        print("evaluation/review.json is not release-ready:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("evaluation/review.json shows a completed independent human review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
