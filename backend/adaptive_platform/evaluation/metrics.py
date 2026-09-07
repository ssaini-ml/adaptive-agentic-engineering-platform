from __future__ import annotations

from collections.abc import Hashable, Iterable, Sequence
from math import isclose

from adaptive_platform.evaluation.models import Score


def precision_recall(
    expected: Iterable[Hashable],
    actual: Iterable[Hashable],
) -> Score:
    expected_set = set(expected)
    actual_set = set(actual)
    true_positive = len(expected_set & actual_set)
    false_positive = len(actual_set - expected_set)
    false_negative = len(expected_set - actual_set)
    precision = true_positive / len(actual_set) if actual_set else float(not expected_set)
    recall = true_positive / len(expected_set) if expected_set else float(not actual_set)
    return Score(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        precision=precision,
        recall=recall,
    )


def cohen_kappa(labels_a: Sequence[str], labels_b: Sequence[str]) -> float:
    if len(labels_a) != len(labels_b):
        raise ValueError("Label sequences must have equal length")
    if not labels_a:
        raise ValueError("At least one paired label is required")

    observed = sum(a == b for a, b in zip(labels_a, labels_b, strict=True)) / len(labels_a)
    categories = set(labels_a) | set(labels_b)
    expected = sum(
        (labels_a.count(category) / len(labels_a))
        * (labels_b.count(category) / len(labels_b))
        for category in categories
    )
    if isclose(expected, 1.0):
        return 1.0 if isclose(observed, 1.0) else 0.0
    return (observed - expected) / (1.0 - expected)

