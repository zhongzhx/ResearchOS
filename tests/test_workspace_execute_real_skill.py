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
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_agent_api as api  # noqa: E402


class WorkspaceExecuteRealSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_workflow_http_"))
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
        api.CONFIG = self.previous_config
        if self.previous_root is None:
            os.environ.pop("RESEARCHOS_AGENT_ROOT", None)
        else:
            os.environ["RESEARCHOS_AGENT_ROOT"] = self.previous_root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(self.base_url + path, data=data, headers={"Content-Type": "application/json"}, method=method)
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_http_workflow_execution_returns_real_run_and_artifacts(self) -> None:
        project = self._request("POST", "/research-os/projects", {"id": "workflow-http", "title": "Workflow HTTP"})["project"]

        result = self._request(
            "POST",
            "/research-os/workflow-executions",
            {"project_id": project["id"], "intent": "nature_academic_polishing", "params": {"text": "  Supplied abstract.  "}},
        )
        artifacts = self._request("GET", f"/research-os/projects/{project['id']}/artifacts")["artifacts"]

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["run_id"])
        self.assertEqual(len(result["artifacts"]), 3)
        self.assertEqual({item["artifact_id"] for item in artifacts}, {item["artifact_id"] for item in result["artifacts"]})

    def test_http_file_registry_is_project_scoped_and_supports_ingest_delete_open_info(self) -> None:
        project_a = self._request("POST", "/research-os/projects", {"id": "files-a", "title": "Files A"})["project"]
        project_b = self._request("POST", "/research-os/projects", {"id": "files-b", "title": "Files B"})["project"]
        artifact = self._request(
            "POST",
            "/research-os/files/register",
            {"project_id": project_a["id"], "source_type": "upload", "display_name": "same.csv", "content": "a,b\n1,2\n"},
        )["artifact"]

        listed_a = self._request("GET", f"/research-os/projects/{project_a['id']}/artifacts")["artifacts"]
        listed_b = self._request("GET", f"/research-os/projects/{project_b['id']}/artifacts")["artifacts"]
        opened = self._request("GET", f"/research-os/projects/{project_a['id']}/artifacts/{artifact['artifact_id']}/open-info")["open_info"]
        indexed = self._request(
            "POST",
            f"/research-os/files/{artifact['artifact_id']}/ingest",
            {"project_id": project_a["id"], "ingest_status": "indexed"},
        )["artifact"]
        deleted = self._request("POST", f"/research-os/files/{artifact['artifact_id']}/delete", {"project_id": project_a["id"]})["artifact"]

        self.assertEqual(len(listed_a), 1)
        self.assertEqual(listed_b, [])
        self.assertEqual(opened["preview_type"], "table")
        self.assertEqual(indexed["kb_status"], "indexed")
        self.assertEqual(deleted["status"], "deleted")
        self.assertTrue(Path(artifact["absolute_path"]).exists())

    def test_http_rag_route_forces_current_project_scope(self) -> None:
        project = self._request("POST", "/research-os/projects", {"id": "rag-http", "title": "RAG HTTP"})["project"]

        with patch.object(api.research_os, "query_research_rag", side_effect=lambda _root, payload: payload):
            result = self._request(
                "POST",
                "/research-os/rag/query",
                {"project_id": project["id"], "question": "test", "retrieval_scope": "cross_project", "cross_project": True},
            )

        self.assertEqual(result["retrieval_scope"], "current_project")
        self.assertFalse(result["cross_project"])


if __name__ == "__main__":
    unittest.main()
