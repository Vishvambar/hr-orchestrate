from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from hackerrank_orchestrator.llm import ProviderError, make_provider


class ProviderSetupTests(unittest.TestCase):
    def test_generic_compatible_provider_can_be_built(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_COMPAT_API_KEY": "dummy",
                "OPENAI_COMPAT_BASE_URL": "https://example.com/v1",
                "OPENAI_COMPAT_MODEL": "demo-model",
            },
            clear=False,
        ):
            provider = make_provider("compat", None)
            self.assertEqual(provider.name, "compat")
            self.assertEqual(provider.model, "demo-model")

    def test_auto_provider_uses_configured_compatible_candidates(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CEREBRAS_API_KEY": "dummy",
                "CEREBRAS_MODEL": "glm-test",
            },
            clear=False,
        ):
            provider = make_provider("auto", None)
            self.assertEqual(provider.name, "auto")
            self.assertEqual(provider.model, "dynamic")

    def test_compat_requires_base_url_and_model(self) -> None:
        with patch.dict(os.environ, {"OPENAI_COMPAT_API_KEY": "dummy"}, clear=True):
            with self.assertRaises(ProviderError):
                make_provider("compat", None)


if __name__ == "__main__":
    unittest.main()
