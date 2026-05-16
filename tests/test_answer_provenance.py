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


class AnswerProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_answer_provenance_"))
        self.agent_root = self.tmp / "agent_data"
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_env = {key: os.environ.get(key) for key in ["LLM_PROVIDER", "TEST_LLM_SENTINEL", "RESEARCHOS_WATCH_AFTER_SKILL_RUN"]}
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

    def _post_chat(self, payload: dict) -> dict:
        request = urllib.request.Request(
            self.base_url + "/research-os/agent/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                self.assertEqual(response.status, 200)
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            self.fail(f"unexpected HTTP {exc.code}: {exc.read().decode('utf-8')}")

    def test_every_chat_response_has_safe_provenance_summary(self) -> None:
        result = self._post_chat({"message": "你好", "project_id": "demo_project"})

        self.assertIn(result["answer_source"], {"llm", "template", "fallback", "validator_rewrite", "sanitizer_rewrite", "coordinator_handoff", "product_demo", "cache", "error_recovery"})
        self.assertIsInstance(result["llm_called"], bool)
        self.assertIsInstance(result["llm_output_used"], bool)
        self.assertIsInstance(result["answer_overwritten_after_llm"], bool)
        self.assertTrue(result["context_compiler_used"])
        self.assertTrue(result["prompt_router_used"])
        self.assertEqual(result["llm_provider"], "mock")
        self.assertNotIn("system_prompt", json.dumps(result, ensure_ascii=False).lower())
        self.assertNotRegex(json.dumps(result, ensure_ascii=False), r"sk-[A-Za-z0-9_-]{8,}")

    def test_template_history_response_is_not_marked_as_llm(self) -> None:
        result = self._post_chat({"message": "我和你对话的第一句话是什么", "project_id": "demo_project"})

        self.assertEqual(result["answer_source"], "template")
        self.assertFalse(result["llm_called"])
        self.assertFalse(result["llm_output_used"])
        self.assertFalse(result["answer_overwritten_after_llm"])
        self.assertFalse(result["prompt_router_used"])


if __name__ == "__main__":
    unittest.main()
