from __future__ import annotations

import unittest

from adaptive_platform.evaluation.metrics import cohen_kappa, precision_recall


class MetricTests(unittest.TestCase):
    def test_precision_recall_reports_all_counts(self) -> None:
        score = precision_recall({"a", "b"}, {"b", "c"})
        self.assertEqual(score.true_positive, 1)
        self.assertEqual(score.false_positive, 1)
        self.assertEqual(score.false_negative, 1)
        self.assertEqual(score.precision, 0.5)
        self.assertEqual(score.recall, 0.5)

    def test_empty_expected_and_actual_is_perfect(self) -> None:
        score = precision_recall(set(), set())
        self.assertEqual(score.precision, 1.0)
        self.assertEqual(score.recall, 1.0)

    def test_cohen_kappa_perfect_agreement(self) -> None:
        self.assertEqual(cohen_kappa(["yes", "no", "yes"], ["yes", "no", "yes"]), 1.0)

    def test_cohen_kappa_requires_paired_labels(self) -> None:
        with self.assertRaisesRegex(ValueError, "equal length"):
            cohen_kappa(["yes"], ["yes", "no"])


if __name__ == "__main__":
    unittest.main()

