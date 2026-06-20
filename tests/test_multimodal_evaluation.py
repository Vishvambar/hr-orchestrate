from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from claim_orchestrator.multimodal_evaluation import evaluate_claim_review_csv


class MultimodalEvaluationTests(unittest.TestCase):
    def test_set_columns_are_compared_order_independently(self) -> None:
        header = [
            "user_id",
            "image_paths",
            "user_claim",
            "claim_object",
            "risk_flags",
            "supporting_image_ids",
            "claim_status",
        ]
        expected_row = {
            "user_id": "u1",
            "image_paths": "a/img_1.jpg;b/img_2.jpg",
            "user_claim": "screen cracked",
            "claim_object": "laptop",
            "risk_flags": "manual_review_required;user_history_risk",
            "supporting_image_ids": "img_2;img_1",
            "claim_status": "supported",
        }
        predicted_row = {
            "user_id": "u1",
            "image_paths": "a/img_1.jpg;b/img_2.jpg",
            "user_claim": "screen cracked",
            "claim_object": "laptop",
            "risk_flags": "user_history_risk;manual_review_required",
            "supporting_image_ids": "img_1;img_2",
            "claim_status": "supported",
        }

        with TemporaryDirectory() as tmpdir:
            expected_path = Path(tmpdir) / "expected.csv"
            predicted_path = Path(tmpdir) / "predicted.csv"
            for path, row in (
                (expected_path, expected_row),
                (predicted_path, predicted_row),
            ):
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=header)
                    writer.writeheader()
                    writer.writerow(row)

            report = evaluate_claim_review_csv(expected_path, predicted_path)
            self.assertEqual(report["overall_normalized_accuracy"], 1.0)
            self.assertEqual(report["row_identity_mismatches"], [])


if __name__ == "__main__":
    unittest.main()
