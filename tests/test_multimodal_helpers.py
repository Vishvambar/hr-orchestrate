from __future__ import annotations

import unittest

from claim_orchestrator.multimodal_helpers import (
    derive_issue_family,
    history_risk_flags,
    normalize_risk_flags,
    parse_claim_issue_type,
    parse_object_part,
    supporting_image_ids,
)


class MultimodalHelpersTests(unittest.TestCase):
    def test_issue_and_object_part_parsing(self) -> None:
        self.assertEqual(parse_claim_issue_type("The windshield has a crack"), "crack")
        self.assertEqual(
            parse_object_part("car", "The front bumper is scratched"), "front_bumper"
        )
        self.assertEqual(derive_issue_family("scratch"), "dent or scratch")

    def test_risk_flag_normalization(self) -> None:
        self.assertEqual(
            normalize_risk_flags(
                ["user_history_risk", "manual_review_required", "user_history_risk"]
            ),
            "manual_review_required;user_history_risk",
        )
        self.assertEqual(supporting_image_ids("a/img_2.jpg;a/img_1.jpg"), "img_1;img_2")

    def test_history_risk_flags(self) -> None:
        flags = history_risk_flags(
            {
                "past_claim_count": "7",
                "last_90_days_claim_count": "3",
                "manual_review_claim": "1",
                "rejected_claim": "0",
                "history_flags": "repeat claimant",
            }
        )
        self.assertIn("user_history_risk", flags)
        self.assertIn("manual_review_required", flags)


if __name__ == "__main__":
    unittest.main()
