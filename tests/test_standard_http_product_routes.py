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
import research_os_mvp as ros  # noqa: E402


class StandardHttpProductRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_http_product_"))
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_env = {
            "RESEARCHOS_AGENT_ROOT": os.environ.get("RESEARCHOS_AGENT_ROOT"),
            "RESEARCHOS_AGENT_DATA_DIR": os.environ.get("RESEARCHOS_AGENT_DATA_DIR"),
            "RESEARCHOS_PRODUCT_API_ENABLED": os.environ.get("RESEARCHOS_PRODUCT_API_ENABLED"),
        }
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.tmp / "agent_data")
        os.environ["RESEARCHOS_AGENT_DATA_DIR"] = str(self.tmp / "agent_data")
        api.CONFIG = api.RuntimeConfig(self.tmp / "agent_data")
        self.project = ros.create_project(api.CONFIG.agent_root, {"id": "product-project", "title": "Product Project"})
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
            with urllib.request.urlopen(self.base_url + path, timeout=30) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _post_json(self, path: str, payload: dict) -> tuple[int, dict]:
        request = urllib.request.Request(self.base_url + path, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_product_api_disabled_returns_disabled_json(self) -> None:
        os.environ["RESEARCHOS_PRODUCT_API_ENABLED"] = "false"

        status, result = self._get_json("/api/product/features")

        self.assertEqual(status, 503)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "disabled")

    def test_product_routes_enabled_list_and_run_feature(self) -> None:
        os.environ["RESEARCHOS_PRODUCT_API_ENABLED"] = "true"

        status, features = self._get_json("/api/product/features")
        missing_status, missing = self._post_json("/api/product/features/data_analysis_workflow/run", {"inline_csv": "group,value\ncontrol,1\nstim,2\n"})
        run_status, run = self._post_json("/api/product/features/data_analysis_workflow/run", {"project_id": self.project["id"], "inline_csv": "group,value\ncontrol,1\nstim,2\n"})
        demo_status, demo = self._post_json("/api/product/features/dual_agent_research_task/demo", {"project_id": self.project["id"]})

        self.assertEqual(status, 200)
        self.assertEqual(features["count"], 8)
        self.assertEqual(missing_status, 400)
        self.assertEqual(missing["error"], "project_id is required")
        self.assertEqual(run_status, 200)
        self.assertTrue(run["ok"])
        self.assertEqual(run["status"], "partial")
        self.assertEqual(demo_status, 200)
        self.assertTrue(demo["ok"])
        self.assertIn("task_lifecycle", demo)


if __name__ == "__main__":
    unittest.main()
