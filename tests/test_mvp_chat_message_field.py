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


class MvpChatMessageFieldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_mvp_chat_"))
        self.agent_root = self.tmp / "agent_data"
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_env = {key: os.environ.get(key) for key in ["LLM_PROVIDER", "RESEARCHOS_WATCH_AFTER_SKILL_RUN"]}
        os.environ["LLM_PROVIDER"] = "mock"
        os.environ["RESEARCHOS_WATCH_AFTER_SKILL_RUN"] = "0"
        api.CONFIG = api.RuntimeConfig(self.agent_root)
        api.research_os.create_project(
            self.agent_root,
            {"id": "demo_project", "title": "Demo Project", "research_area": "ResearchOS client acceptance"},
        )
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

    def _post_json(self, payload: dict) -> dict:
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

    def test_message_field_returns_natural_assistant_answer(self) -> None:
        result = self._post_json(
            {"message": "\u4f60\u597d\uff0c\u4f60\u73b0\u5728\u53ef\u4ee5\u6b63\u5e38\u56de\u7b54\u5417\uff1f", "project_id": "demo_project"}
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result.get("answer"))
        self.assertNotIn("\u95ee\u9898\u4e0d\u5b8c\u6574", result["answer"])
        self.assertNotIn("Execution completed", result["answer"])
        self.assertNotIn("task_type=research_planning", result["answer"])
        self.assertNotRegex(json.dumps(result, ensure_ascii=False), r"sk-[A-Za-z0-9_-]{8,}")

    def test_chat_accepts_user_query_query_and_content_aliases(self) -> None:
        cases = [
            ("user_query", "\u4f60\u80fd\u6b63\u5e38\u56de\u7b54\u5417"),
            ("query", "\u4f60\u662f\u4ec0\u4e48"),
            ("content", "\u4ecb\u7ecd\u4e00\u4e0b\u5f53\u524d\u9879\u76ee"),
        ]

        for field, value in cases:
            with self.subTest(field=field):
                result = self._post_json({field: value, "project_id": "demo_project"})
                self.assertTrue(result["ok"])
                self.assertTrue(result.get("answer"))
                messages = api.research_os.list_chat_messages(
                    self.agent_root,
                    result["conversation_id"],
                    "demo_project",
                    limit=5,
                )
                self.assertEqual(messages[-2]["role"], "user")
                self.assertEqual(messages[-2]["content"], value)


if __name__ == "__main__":
    unittest.main()
