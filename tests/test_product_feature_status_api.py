import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_agent_api as api  # noqa: E402


class ProductFeatureStatusApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_product_api_"))
        self.previous_config = getattr(api, "CONFIG", None)
        api.CONFIG = api.RuntimeConfig(self.tmp / "agent_data")
        self.previous_env = {"RESEARCHOS_AGENT_ROOT": os.environ.get("RESEARCHOS_AGENT_ROOT")}
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.tmp / "agent_data")
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

    def test_features_endpoint_lists_all_product_flows(self) -> None:
        response = self._get_json("/api/product/features")

        self.assertTrue(response["ok"])
        self.assertEqual(response["count"], 8)
        self.assertTrue(any(feature["feature_id"] == "literature_harvest_workflow" for feature in response["features"]))

    def test_feature_detail_and_run_return_lifecycle_shape(self) -> None:
        detail = self._get_json("/api/product/features/dual_agent_research_task")
        run = self._post_json(
            "/api/product/features/dual_agent_research_task/run",
            {"project_id": "demo_project", "user_query": "Design RAW264.7 innate immune activation experiment", "mode": "demo"},
        )

        self.assertEqual(detail["feature"]["feature_id"], "dual_agent_research_task")
        self.assertTrue(run["ok"])
        self.assertEqual(run["feature_id"], "dual_agent_research_task")
        self.assertIn(run["status"], {"ready", "partial"})
        self.assertIn("task_lifecycle", run)
        self.assertIn("handoff", run)


if __name__ == "__main__":
    unittest.main()
