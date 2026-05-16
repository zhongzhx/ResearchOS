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
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_agent_api as api  # noqa: E402


class StandardHttpDualAgentPostRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_http_dual_"))
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_env = {
            "RESEARCHOS_AGENT_ROOT": os.environ.get("RESEARCHOS_AGENT_ROOT"),
            "RESEARCHOS_AGENT_DATA_DIR": os.environ.get("RESEARCHOS_AGENT_DATA_DIR"),
            "RESEARCHOS_DUAL_AGENT_API_ENABLED": os.environ.get("RESEARCHOS_DUAL_AGENT_API_ENABLED"),
        }
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.tmp / "agent_data")
        os.environ["RESEARCHOS_AGENT_DATA_DIR"] = str(self.tmp / "agent_data")
        api.CONFIG = api.RuntimeConfig(self.tmp / "agent_data")
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

    def _post_json(self, path: str, payload: dict) -> tuple[int, dict]:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_coordinator_run_disabled_by_switch(self) -> None:
        os.environ["RESEARCHOS_DUAL_AGENT_API_ENABLED"] = "false"

        status, result = self._post_json("/api/agents/coordinator/run", {"user_query": "hello"})

        self.assertEqual(status, 503)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "disabled")

    def test_coordinator_run_enabled_returns_stable_json(self) -> None:
        os.environ["RESEARCHOS_DUAL_AGENT_API_ENABLED"] = "true"

        status, result = self._post_json("/api/agents/coordinator/run", {"user_query": "summarize project status", "project_id": "p1"})

        self.assertEqual(status, 200)
        self.assertIn("ok", result)
        self.assertIn("execution_result", result)

    def test_coordinator_placeholder_result_falls_back_to_mvp_chat(self) -> None:
        os.environ["RESEARCHOS_DUAL_AGENT_API_ENABLED"] = "true"
        placeholder = {
            "ok": True,
            "answer": "Execution completed. task_type=research_planning",
            "task_spec": {"task_type": "research_planning", "user_query": "今天我想先跟你聊一下项目思路"},
            "execution_result": {"status": "success", "summary": "Execution completed. task_type=research_planning"},
            "research_task": {"artifacts": []},
        }

        with patch("backend.researchos.api.dual_agent_routes.coordinator_run", return_value=placeholder), patch.object(
            api.research_os,
            "agent_chat",
            return_value={"ok": True, "answer": "legacy chat answer", "conversation_id": "c1"},
        ) as legacy_chat:
            status, result = self._post_json(
                "/api/agents/coordinator/run",
                {"user_query": "今天我想先跟你聊一下项目思路", "project_id": "p1", "conversation_id": "c1"},
            )

        self.assertEqual(status, 200)
        self.assertEqual(result["answer"], "legacy chat answer")
        self.assertEqual(result["fallback_used"], "mvp_agent_chat")
        legacy_chat.assert_called_once()

    def test_skills_route_post_is_available_when_enabled(self) -> None:
        os.environ["RESEARCHOS_DUAL_AGENT_API_ENABLED"] = "true"

        status, result = self._post_json("/api/skills/route", {"query": "search papers about macrophages"})

        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])
        self.assertIn("pipeline", result)


if __name__ == "__main__":
    unittest.main()
