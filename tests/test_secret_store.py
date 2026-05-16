import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.settings.secret_store import (
    delete_llm_settings,
    load_llm_secret_for_agent,
    load_llm_settings_summary,
    mask_secret,
    redact_secrets_in_obj,
    save_llm_settings,
)


class SecretStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_secret_store_"))
        self.previous = {
            "RESEARCHOS_AGENT_DATA_DIR": os.environ.get("RESEARCHOS_AGENT_DATA_DIR"),
            "LLM_PROVIDER": os.environ.get("LLM_PROVIDER"),
            "LLM_API_KEY": os.environ.get("LLM_API_KEY"),
            "LLM_BASE_URL": os.environ.get("LLM_BASE_URL"),
            "LLM_MODEL": os.environ.get("LLM_MODEL"),
            "MINIMAX_API_KEY": os.environ.get("MINIMAX_API_KEY"),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "BRAIN_AGENT_API_KEY": os.environ.get("BRAIN_AGENT_API_KEY"),
            "EXECUTION_AGENT_API_KEY": os.environ.get("EXECUTION_AGENT_API_KEY"),
        }
        os.environ["RESEARCHOS_AGENT_DATA_DIR"] = str(self.tmp / "agent_data")
        for key in ["LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "MINIMAX_API_KEY", "OPENAI_API_KEY", "BRAIN_AGENT_API_KEY", "EXECUTION_AGENT_API_KEY"]:
            os.environ[key] = ""

    def tearDown(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_summary_masks_keys_and_agent_secret_isolated(self) -> None:
        save_llm_settings(
            {
                "mode": "separate_keys",
                "brain_agent": {"provider": "openai", "model": "brain-model", "api_key": "sk-brain-secret"},
                "execution_agent": {"provider": "minimax", "model": "exec-model", "api_key": "sk-exec-secret"},
            }
        )

        summary = load_llm_settings_summary()
        brain = load_llm_secret_for_agent("brain_agent")
        execution = load_llm_secret_for_agent("execution_agent")
        stored = (self.tmp / "agent_data" / "secrets" / "llm_settings.json").read_text(encoding="utf-8")

        self.assertEqual(summary["mode"], "separate_keys")
        self.assertEqual(summary["brain_agent"]["masked_key"], "****cret")
        self.assertNotIn("api_key", summary["brain_agent"])
        self.assertEqual(brain["api_key"], "sk-brain-secret")
        self.assertEqual(execution["api_key"], "sk-exec-secret")
        self.assertNotEqual(brain["api_key"], execution["api_key"])
        self.assertNotIn("sk-brain-secret", stored)
        self.assertNotIn("sk-exec-secret", stored)

    def test_redact_secrets_recurses_through_objects(self) -> None:
        redacted = redact_secrets_in_obj({"token": "abc12345", "nested": ["OPENAI_API_KEY=sk-test-secret"]})

        serialized = json.dumps(redacted)
        self.assertNotIn("abc12345", serialized)
        self.assertNotIn("sk-test-secret", serialized)
        self.assertEqual(mask_secret(""), "")

    def test_delete_llm_settings_removes_local_file(self) -> None:
        save_llm_settings({"mode": "single_key", "provider": "openai", "api_key": "sk-delete-secret"})

        result = delete_llm_settings()

        self.assertTrue(result["ok"])
        self.assertEqual(load_llm_settings_summary()["mode"], "not_configured")


if __name__ == "__main__":
    unittest.main()
