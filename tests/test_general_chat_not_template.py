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


SENTINEL = "SENTINEL_MODEL_OUTPUT_ResearchOS_12345"


class GeneralChatNotTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_general_chat_"))
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

    def test_plain_chat_messages_use_llm_source(self) -> None:
        messages = [
            "你好",
            "你可以为我做什么",
            "你是什么",
            "介绍一下 ResearchOS",
            "怎么使用你",
            "你能帮我做什么",
            "当前系统正常吗",
            "介绍一下当前项目",
        ]
        for message in messages:
            with self.subTest(message=message):
                response = ros.agent_chat(self.agent_root, {"project_id": "demo_project", "message": message})

                self.assertEqual(response["answer_source"], "llm")
                self.assertTrue(response["llm_called"])
                self.assertTrue(response["llm_output_used"])
                self.assertIn(SENTINEL, response["answer"])
                self.assertNotIn("Research Task Handoff", response["answer"])
                self.assertNotIn("当前问题似乎不完整", response["answer"])


if __name__ == "__main__":
    unittest.main()
