import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class BackendChatSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_chat_smoke_"))
        self.agent_root = self.tmp / "agent_data"
        self.previous_env = {key: os.environ.get(key) for key in ["LLM_PROVIDER", "TEST_LLM_SENTINEL", "RESEARCHOS_WATCH_AFTER_SKILL_RUN"]}
        os.environ["LLM_PROVIDER"] = "mock"
        os.environ["TEST_LLM_SENTINEL"] = "true"
        os.environ["RESEARCHOS_WATCH_AFTER_SKILL_RUN"] = "0"
        self.project = ros.create_project(self.agent_root, {"id": "smoke-project", "title": "Smoke Project"})

    def tearDown(self) -> None:
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_selected_project_chat_returns_natural_language_answer(self) -> None:
        result = ros.agent_chat(
            self.agent_root,
            {
                "message": "你好",
                "project_id": self.project["id"],
                "conversation_id": "smoke_conversation",
                "session_id": "smoke_session",
            },
        )

        answer = result.get("answer") or result.get("content") or result.get("message") or ""
        self.assertTrue(result.get("ok"))
        self.assertTrue(answer.strip())
        self.assertNotIn("Research Task Handoff", answer)
        self.assertNotIn("TaskSpec", answer)
        self.assertNotIn("ExecutionResult", answer)

    def test_chat_does_not_auto_create_default_project(self) -> None:
        with self.assertRaisesRegex(KeyError, "project not found"):
            ros.agent_chat(self.agent_root, {"message": "你好", "project_id": "default"})

    def test_chat_rejects_when_conversation_id_belongs_to_another_project(self) -> None:
        alpha = ros.create_project(self.agent_root, {"id": "alpha_project", "title": "Alpha Project"})
        beta = ros.create_project(self.agent_root, {"id": "beta_project", "title": "Beta Project"})
        ros.ensure_chat_session(self.agent_root, alpha["id"], "shared_chat_session", title="Alpha chat")

        with self.assertRaisesRegex(ValueError, "belongs to a different project"):
            ros.agent_chat(
                self.agent_root,
                {
                    "message": "你好",
                    "project_id": beta["id"],
                    "conversation_id": "shared_chat_session",
                    "session_id": "shared_chat_session",
                },
            )


if __name__ == "__main__":
    unittest.main()
