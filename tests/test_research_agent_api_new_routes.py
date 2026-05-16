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


class ResearchAgentApiNewRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_new_routes_"))
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_env = {key: os.environ.get(key) for key in [
            "RESEARCHOS_AGENT_ROOT",
            "RESEARCHOS_AGENT_DATA_DIR",
            "RESEARCHOS_DUAL_AGENT_API_ENABLED",
            "RESEARCHOS_PRODUCT_API_ENABLED",
            "RESEARCHOS_MEMORYOS_ENABLED",
        ]}
        agent_root = self.tmp / "agent_data"
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(agent_root)
        os.environ["RESEARCHOS_AGENT_DATA_DIR"] = str(agent_root)
        api.CONFIG = api.RuntimeConfig(agent_root)
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

    def _get_json(self, path: str) -> tuple[int, dict]:
        try:
            with urllib.request.urlopen(self.base_url + path, timeout=20) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _post_json(self, path: str, payload: dict) -> tuple[int, dict]:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_coordinator_route_respects_disabled_gate(self) -> None:
        os.environ["RESEARCHOS_DUAL_AGENT_API_ENABLED"] = "false"

        status, result = self._post_json("/api/agents/coordinator/run", {"user_query": "hello"})

        self.assertEqual(status, 503)
        self.assertEqual(result["status"], "disabled")

    def test_product_and_memory_routes_are_served_by_mvp_http_adapter(self) -> None:
        os.environ["RESEARCHOS_PRODUCT_API_ENABLED"] = "true"
        os.environ["RESEARCHOS_MEMORYOS_ENABLED"] = "true"

        product_status, product = self._get_json("/api/product/features")
        memory_status, memory = self._get_json("/api/memory/working?project_id=test_project")

        self.assertEqual(product_status, 200)
        self.assertEqual(product["count"], 8)
        self.assertEqual(memory_status, 200)
        self.assertIn("working_memory", memory)

    def test_llm_delete_route_is_available_and_redacted(self) -> None:
        status, result = self._post_json("/api/settings/llm", {"mode": "single_key", "provider": "mock", "api_key": "sk-secret-value"})
        delete_request = urllib.request.Request(self.base_url + "/api/settings/llm", method="DELETE")
        with urllib.request.urlopen(delete_request, timeout=20) as response:
            delete_status = response.status
            delete_result = json.loads(response.read().decode("utf-8"))

        self.assertEqual(status, 200)
        self.assertNotIn("sk-secret-value", json.dumps(result))
        self.assertEqual(delete_status, 200)
        self.assertTrue(delete_result["deleted"])


if __name__ == "__main__":
    unittest.main()
