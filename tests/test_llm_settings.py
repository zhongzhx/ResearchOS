import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.settings.llm_settings import get_llm_settings_summary, resolve_llm_mode, test_llm_settings, update_llm_settings


class LlmSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_llm_settings_"))
        self.previous = os.environ.get("RESEARCHOS_AGENT_DATA_DIR")
        os.environ["RESEARCHOS_AGENT_DATA_DIR"] = str(self.tmp / "agent_data")

    def tearDown(self) -> None:
        if self.previous is None:
            os.environ.pop("RESEARCHOS_AGENT_DATA_DIR", None)
        else:
            os.environ["RESEARCHOS_AGENT_DATA_DIR"] = self.previous
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_update_single_key_returns_redacted_summary(self) -> None:
        result = update_llm_settings({"mode": "single_key", "provider": "openai", "model": "gpt-test", "api_key": "sk-single-secret"})

        self.assertTrue(result["ok"])
        self.assertEqual(resolve_llm_mode(), "single_key")
        self.assertEqual(result["brain_agent"]["masked_key"], "****cret")
        self.assertEqual(result["execution_agent"]["masked_key"], "****cret")
        self.assertNotIn("sk-single-secret", str(result))

    def test_subscription_mode_does_not_expose_token(self) -> None:
        result = update_llm_settings({"mode": "subscription", "subscription": {"token": "sub-secret-token", "workspace_id": "ws1"}})

        self.assertTrue(result["ok"])
        self.assertTrue(result["subscription"]["enabled"])
        self.assertNotIn("sub-secret-token", str(get_llm_settings_summary()))

    def test_test_llm_settings_supports_both_targets(self) -> None:
        update_llm_settings({"mode": "single_key", "provider": "mock", "model": "mock-model"})

        result = test_llm_settings("both")

        self.assertTrue(result["ok"])
        self.assertTrue(result["brain_agent"]["ok"])
        self.assertTrue(result["execution_agent"]["ok"])


if __name__ == "__main__":
    unittest.main()
