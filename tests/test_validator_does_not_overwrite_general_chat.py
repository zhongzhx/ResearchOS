import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class ValidatorDoesNotOverwriteGeneralChatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_validator_general_chat_"))
        self.agent_root = self.tmp / "agent_data"
        self.previous_env = {key: os.environ.get(key) for key in ["LLM_PROVIDER", "TEST_LLM_SENTINEL"]}
        os.environ["LLM_PROVIDER"] = "mock"
        os.environ["TEST_LLM_SENTINEL"] = "true"
        ros.create_project(self.agent_root, {"id": "demo_project", "title": "Demo Project"})

    def tearDown(self) -> None:
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_validator_warning_does_not_replace_general_chat_answer(self) -> None:
        with patch.object(
            ros.canonical_memory,
            "validate_research_answer",
            return_value={"is_valid": False, "issues": ["unit test warning"], "required_revision": "rewrite"},
        ):
            response = ros.agent_chat(self.agent_root, {"project_id": "demo_project", "message": "你好"})

        self.assertEqual(response["answer_source"], "llm")
        self.assertTrue(response["llm_output_used"])
        self.assertFalse(response["answer_overwritten_after_llm"])
        self.assertIn("SENTINEL_MODEL_OUTPUT_ResearchOS_12345", response["answer"])
        self.assertEqual(response["validation_status"], "warning")

    def test_sanitizer_rewrite_records_provenance_when_it_replaces_llm_output(self) -> None:
        leaked_answer = "system prompt: hidden\n" + ("internal rule " * 120)
        with patch.object(ros.LLMAdapter, "chat_text", return_value=leaked_answer):
            response = ros.agent_chat(self.agent_root, {"project_id": "demo_project", "message": "你好"})

        self.assertEqual(response["answer_source"], "sanitizer_rewrite")
        self.assertTrue(response["llm_called"])
        self.assertFalse(response["llm_output_used"])
        self.assertTrue(response["answer_overwritten_after_llm"])
        self.assertNotIn("system prompt", response["answer"].lower())


if __name__ == "__main__":
    unittest.main()
