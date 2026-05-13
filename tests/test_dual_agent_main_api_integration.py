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
SCRIPTS = ROOT / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_agent_api as api  # noqa: E402


class DualAgentMainApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_main_api_"))
        self.agent_root = self.tmp / "agent_data"
        self.previous_config = getattr(api, "CONFIG", None)
        api.CONFIG = api.RuntimeConfig(self.agent_root)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.previous_env = {
            "RESEARCHOS_DUAL_AGENT_API_ENABLED": os.environ.get("RESEARCHOS_DUAL_AGENT_API_ENABLED"),
            "RESEARCHOS_AGENT_ROOT": os.environ.get("RESEARCHOS_AGENT_ROOT"),
            "RESEARCH_BRAIN_ROOT": os.environ.get("RESEARCH_BRAIN_ROOT"),
            "RESEARCHOS_SKILLS_ROOT": os.environ.get("RESEARCHOS_SKILLS_ROOT"),
        }
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.agent_root)
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        os.environ["RESEARCHOS_SKILLS_ROOT"] = str(self.tmp / "skills")

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

    def _get_json(self, path: str) -> dict:
        with urllib.request.urlopen(self.base_url + path, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post_json(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_dual_agent_routes_are_disabled_by_default(self) -> None:
        os.environ.pop("RESEARCHOS_DUAL_AGENT_API_ENABLED", None)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get_json("/api/demo/dual-agent")
        self.assertEqual(ctx.exception.code, 503)
        self.assertEqual(json.loads(ctx.exception.read().decode("utf-8"))["error"], "dual_agent_api_disabled")
        ctx.exception.close()

        with self.assertRaises(urllib.error.HTTPError) as post_ctx:
            self._post_json("/api/agents/coordinator/run", {"project_id": "p1", "user_query": "write report"})
        self.assertEqual(post_ctx.exception.code, 503)
        self.assertEqual(json.loads(post_ctx.exception.read().decode("utf-8"))["error"], "dual_agent_api_disabled")
        post_ctx.exception.close()

    def test_runtime_status_endpoint_reports_demo_runtime_boundary(self) -> None:
        response = self._get_json("/research-os/runtime/status")

        self.assertEqual(response["active_runtime"], "research-agent-runtime")
        self.assertEqual(response["connected_modules"]["chat"], "research_os_mvp.agent_chat")
        self.assertEqual(response["connected_modules"]["literature_harvest"], "research_os_mvp literature workflow")
        self.assertIn("backend/researchos dual-agent scaffold", response["scaffold_modules"])
        self.assertIn("chat", response["demo_safe_modules"])
        self.assertIn("call_tool:pdf_parser", response["disconnected_modules"])

    def test_dual_agent_demo_route_is_available_when_enabled(self) -> None:
        os.environ["RESEARCHOS_DUAL_AGENT_API_ENABLED"] = "true"
        response = self._get_json("/api/demo/dual-agent?project_id=api_demo_project")
        self.assertTrue(response["ok"])
        self.assertIn("task_type", response)
        self.assertIn("skillrun_id", response)

    def test_skill_library_routes_are_available_when_enabled(self) -> None:
        os.environ["RESEARCHOS_DUAL_AGENT_API_ENABLED"] = "true"
        catalog = self._get_json("/api/skills/catalog")
        pipelines = self._get_json("/api/skills/pipelines")
        routed = self._post_json("/api/skills/route", {"user_query": "分析 CSV 并写结果段"})

        self.assertTrue(catalog["ok"])
        self.assertTrue(any(row["skill_id"] == "skill-output-validator" for row in catalog["skills"]))
        self.assertTrue(any(row["pipeline_name"] == "data_analysis_to_narrative" for row in pipelines["pipelines"]))
        self.assertEqual(routed["pipeline"]["pipeline_name"], "data_analysis_to_narrative")

    def test_legacy_agent_chat_route_is_unchanged(self) -> None:
        original_agent_chat = api.research_os.agent_chat

        def fake_agent_chat(agent_root: Path, payload: dict) -> dict:
            return {"ok": True, "answer": "legacy route", "payload": payload}

        api.research_os.agent_chat = fake_agent_chat
        try:
            os.environ["RESEARCHOS_DUAL_AGENT_API_ENABLED"] = "true"
            response = self._post_json("/research-os/agent/chat", {"message": "hello"})
            self.assertEqual(response["answer"], "legacy route")
            self.assertEqual(response["payload"]["message"], "hello")
        finally:
            api.research_os.agent_chat = original_agent_chat


if __name__ == "__main__":
    unittest.main()
