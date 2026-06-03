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


class StandardHttpProjectWorkspaceRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_http_workspace_"))
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_root = os.environ.get("RESEARCHOS_AGENT_ROOT")
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.tmp / "agent_data")
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
        if self.previous_root is None:
            os.environ.pop("RESEARCHOS_AGENT_ROOT", None)
        else:
            os.environ["RESEARCHOS_AGENT_ROOT"] = self.previous_root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _request(self, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_project_workspace_and_artifact_routes_are_project_scoped(self) -> None:
        _, created_a = self._request("POST", "/research-os/projects", {"id": "http-a", "title": "HTTP A"})
        _, created_b = self._request("POST", "/research-os/projects", {"id": "http-b", "title": "HTTP B"})
        project_a = created_a["project"]
        project_b = created_b["project"]

        workspace_status, workspace = self._request("GET", f"/research-os/workspace-state?project_id={project_a['id']}")
        artifact_status, archived = self._request(
            "POST",
            "/research-os/artifacts",
            {"project_id": project_a["id"], "filename": "report.md", "content": "# Real report", "artifact_type": "markdown"},
        )
        _, listed_a = self._request("GET", f"/research-os/artifacts?project_id={project_a['id']}")
        _, listed_b = self._request("GET", f"/research-os/artifacts?project_id={project_b['id']}")

        self.assertEqual(workspace_status, 200)
        self.assertEqual(workspace["project_workspace"]["rag"]["default_scope"], "current_project")
        self.assertEqual(artifact_status, 200)
        self.assertTrue(Path(archived["artifact"]["path"]).is_file())
        self.assertEqual(len(listed_a["artifacts"]), 1)
        self.assertEqual(listed_b["artifacts"], [])


if __name__ == "__main__":
    unittest.main()
