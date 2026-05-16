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


class DemoTaskStatusFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_task_filter_"))
        self.agent_root = self.tmp / "agent_data"
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_env = {key: os.environ.get(key) for key in ["LLM_PROVIDER", "RESEARCHOS_WATCH_AFTER_SKILL_RUN"]}
        os.environ["LLM_PROVIDER"] = "mock"
        os.environ["RESEARCHOS_WATCH_AFTER_SKILL_RUN"] = "0"
        api.CONFIG = api.RuntimeConfig(self.agent_root)
        api.research_os.create_project(self.agent_root, {"id": "demo_project", "title": "Demo Project"})
        for index in range(12):
            api.research_os.start_service_skill_run(
                self.agent_root,
                f"product_demo_{index}",
                "ResearchOS Product Demo",
                "demo_project",
                {"project_id": "demo_project", "index": index},
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

    def test_plain_chat_does_not_return_bulk_demo_task_status(self) -> None:
        result = self._post_json({"message": "\u4f60\u597d", "project_id": "demo_project"})

        self.assertTrue(result["ok"])
        self.assertNotIn("task_status", result)
        self.assertIn("task_status_summary", result)
        self.assertNotIn("ResearchOS Product Demo", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("ResearchOS Product Demo", json.dumps(result.get("task_status_summary"), ensure_ascii=False))

    def test_self_description_chat_does_not_return_demo_task_status(self) -> None:
        result = self._post_json({"message": "\u4f60\u662f\u4ec0\u4e48\u5927\u6a21\u578b", "project_id": "demo_project"})

        self.assertTrue(result["ok"])
        self.assertNotIn("task_status", result)
        self.assertNotIn("ResearchOS Product Demo", json.dumps(result, ensure_ascii=False))

    def test_explicit_task_status_request_can_return_full_status(self) -> None:
        result = self._post_json(
            {"message": "\u5237\u65b0\u4efb\u52a1\u8fdb\u5ea6", "project_id": "demo_project", "include_task_status": True}
        )

        self.assertTrue(result["ok"])
        self.assertIn("task_status", result)
        self.assertTrue(result["task_status"])


if __name__ == "__main__":
    unittest.main()
