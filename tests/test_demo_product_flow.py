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
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_agent_api as api  # noqa: E402
import research_os_mvp as ros  # noqa: E402


class DemoProductFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_demo_product_"))
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_agent_root = os.environ.get("RESEARCHOS_AGENT_ROOT")
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.tmp / "agent_data")
        api.CONFIG = api.RuntimeConfig(self.tmp / "agent_data")
        ros.create_project(api.CONFIG.agent_root, {"id": "demo_project", "title": "Demo Project"})
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
        if self.previous_agent_root is None:
            os.environ.pop("RESEARCHOS_AGENT_ROOT", None)
        else:
            os.environ["RESEARCHOS_AGENT_ROOT"] = self.previous_agent_root
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

    def test_product_demo_flow_is_local_and_complete_without_api_key(self) -> None:
        preview = self._get_json("/api/demo/product-flow?project_id=demo_project")
        run = self._post_json("/api/demo/product-flow/run", {"project_id": "demo_project"})

        for payload in [preview, run]:
            with self.subTest(kind=payload.get("feature_id")):
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["selected_pipeline"], "experiment_design")
                self.assertTrue(payload["required_skills"])
                self.assertTrue(payload["artifacts"])
                self.assertTrue(payload["validation_report"])
                self.assertTrue(payload["memory_update"])
                self.assertIn("TaskSpec", payload["raw_details"])


if __name__ == "__main__":
    unittest.main()
