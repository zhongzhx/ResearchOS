import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_agent_api as api  # noqa: E402


SENTINEL = "SENTINEL_MODEL_OUTPUT_ResearchOS_12345"


class LlmSentinelChatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_sentinel_chat_"))
        self.agent_root = self.tmp / "agent_data"
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_env = {
            key: os.environ.get(key)
            for key in ["LLM_PROVIDER", "TEST_LLM_SENTINEL", "RESEARCHOS_WATCH_AFTER_SKILL_RUN"]
        }
        os.environ["LLM_PROVIDER"] = "mock"
        os.environ["TEST_LLM_SENTINEL"] = "true"
        os.environ["RESEARCHOS_WATCH_AFTER_SKILL_RUN"] = "0"
        api.CONFIG = api.RuntimeConfig(self.agent_root)
        api.research_os.create_project(self.agent_root, {"id": "demo_project", "title": "Demo Project"})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        if self.previous_config is not None:
            api.CONFIG = self.previous_config
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _post_chat(self, message: str) -> dict:
        request = urllib.request.Request(
            self.base_url + "/research-os/agent/chat",
            data=json.dumps({"message": message, "project_id": "demo_project"}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                self.assertEqual(response.status, 200)
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            self.fail(f"unexpected HTTP {exc.code}: {exc.read().decode('utf-8')}")

    def test_general_chat_final_answer_uses_llm_sentinel(self) -> None:
        result = self._post_chat("你好，你现在可以正常回答吗？")

        self.assertTrue(result["ok"])
        self.assertEqual(result["answer_source"], "llm")
        self.assertTrue(result["llm_called"])
        self.assertTrue(result["llm_output_used"])
        self.assertFalse(result["answer_overwritten_after_llm"])
        self.assertIn(SENTINEL, result["answer"])
        self.assertNotIn("当前问题似乎不完整", result["answer"])
        self.assertNotIn("Research Task Handoff", result["answer"])
        self.assertNotIn("ResearchOS Product Demo", json.dumps(result, ensure_ascii=False))

    def test_capability_and_identity_questions_use_llm_not_templates(self) -> None:
        for message in ["你可以为我做什么", "你是什么", "你有什么功能", "怎么使用你"]:
            with self.subTest(message=message):
                result = self._post_chat(message)
                self.assertEqual(result["answer_source"], "llm")
                self.assertTrue(result["llm_called"])
                self.assertTrue(result["llm_output_used"])
                self.assertIn(SENTINEL, result["answer"])
                self.assertNotIn("Research Task Handoff", result["answer"])


if __name__ == "__main__":
    unittest.main()
