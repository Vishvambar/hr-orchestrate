from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

from claim_orchestrator.pipeline import run_contract
from claim_orchestrator.utils import project_root


class DemoPipelineTests(unittest.TestCase):
    def test_demo_pipeline_matches_expected_output(self) -> None:
        summary = run_contract(
            "examples/demo_challenge/contract.toml",
            provider_name="rule-based",
        )
        root = project_root()

        expected_path = root / "examples/demo_challenge/expected/output.csv"
        predicted_path = root / summary.output_csv

        with expected_path.open("r", encoding="utf-8", newline="") as handle:
            expected_rows = list(csv.DictReader(handle))
        with predicted_path.open("r", encoding="utf-8", newline="") as handle:
            predicted_rows = list(csv.DictReader(handle))

        self.assertEqual(expected_rows, predicted_rows)
        self.assertIsNotNone(summary.evaluation_path)

        report = json.loads(
            (root / summary.evaluation_path).read_text(encoding="utf-8")
        )
        self.assertEqual(report["overall_normalized_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
