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


class StandardHttpMemoryRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_http_memory_"))
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_env = {
            "RESEARCHOS_AGENT_ROOT": os.environ.get("RESEARCHOS_AGENT_ROOT"),
            "RESEARCHOS_AGENT_DATA_DIR": os.environ.get("RESEARCHOS_AGENT_DATA_DIR"),
            "RESEARCHOS_MEMORYOS_ENABLED": os.environ.get("RESEARCHOS_MEMORYOS_ENABLED"),
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
        request = urllib.request.Request(self.base_url + path, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_memory_api_disabled_returns_disabled_json(self) -> None:
        os.environ["RESEARCHOS_MEMORYOS_ENABLED"] = "false"

        status, result = self._post_json("/api/memory/search", {"query": "x"})

        self.assertEqual(status, 503)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "disabled")

    def test_memory_search_enabled_returns_json(self) -> None:
        os.environ["RESEARCHOS_MEMORYOS_ENABLED"] = "true"

        status, result = self._post_json("/api/memory/search", {"query": "x", "project_id": "p1"})

        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])
        self.assertIn("results", result)

    def test_memory_search_enabled_requires_project_id(self) -> None:
        os.environ["RESEARCHOS_MEMORYOS_ENABLED"] = "true"

        status, result = self._post_json("/api/memory/search", {"query": "x"})

        self.assertEqual(status, 400)
        self.assertIn("project_id is required", result["error"])


if __name__ == "__main__":
    unittest.main()
