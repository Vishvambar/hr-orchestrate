from __future__ import annotations

import unittest

from hackerrank_orchestrator.pipeline import inspect_contract


class RetrievalTests(unittest.TestCase):
    def test_duplicate_charge_query_hits_billing_first(self) -> None:
        results = inspect_contract(
            "examples/demo_challenge/contract.toml",
            "I was charged twice for my monthly plan",
        )
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(
            results[0]["source_path"],
            "examples/demo_challenge/corpus/billing_refunds.md",
        )

    def test_password_query_hits_account_doc(self) -> None:
        results = inspect_contract(
            "examples/demo_challenge/contract.toml",
            "I forgot my password and lost access to my email",
        )
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(
            results[0]["source_path"],
            "examples/demo_challenge/corpus/account_access.md",
        )


if __name__ == "__main__":
    unittest.main()
