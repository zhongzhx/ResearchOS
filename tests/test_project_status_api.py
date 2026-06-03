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


class ProjectStatusApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_project_status_api_"))
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_root = os.environ.get("RESEARCHOS_AGENT_ROOT")
        self.agent_root = self.tmp / "agent_root"
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.agent_root)
        api.CONFIG = api.RuntimeConfig(self.agent_root)
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
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(self.base_url + path, data=body, headers={"Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_status_and_paths_routes_expose_real_project_state(self) -> None:
        _, created = self._request("POST", "/research-os/projects", {"id": "status-a", "title": "Status A"})
        project = created["project"]
        self._request("POST", "/research-os/files", {"project_id": project["id"], "filename": "input.csv", "content": "a,b\n1,2"})
        self._request("POST", "/research-os/artifacts", {"project_id": project["id"], "filename": "report.md", "content": "# Report"})

        status_code, status_payload = self._request("GET", f"/research-os/projects/{project['id']}/status")
        paths_code, paths_payload = self._request("GET", f"/research-os/projects/{project['id']}/paths")

        self.assertEqual(status_code, 200)
        status = status_payload["project_status"]
        self.assertEqual(status["project_id"], project["id"])
        self.assertEqual(status["root_path"], str(self.agent_root / "projects" / project["id"]))
        self.assertEqual(status["file_count"], 1)
        self.assertGreaterEqual(status["artifact_count"], 1)
        self.assertIn("kb_status", status)
        self.assertIn("rag_status", status)
        self.assertIn("latest_workflow_run", status)
        self.assertEqual(paths_code, 200)
        self.assertEqual(paths_payload["paths"]["root_path"], status["root_path"])
        self.assertIn("debug_log_path", paths_payload["paths"])

    def test_unscoped_reads_return_friendly_errors(self) -> None:
        self._request("POST", "/research-os/projects", {"id": "status-a", "title": "Status A"})

        for path in [
            "/research-os/workspace-state",
            "/research-os/files",
            "/research-os/reference-chunks",
            "/research-os/knowledge-base-entries",
            "/research-os/rag-queries",
            "/research-os/literature/search-tasks",
            "/research-os/skill-runs",
            "/research-os/workflow-board",
            "/research-os/agent-feed",
            "/research-os/artifacts",
            "/research-os/literature/paper-requests",
            "/research-os/literature/unmatched-pdfs",
            "/research-os/failure-logs",
            "/research-os/experiment-logs",
            "/research-os/weekly-digest/configs",
            "/research-os/weekly-digest/reports",
            "/research-os/agent-memory",
            "/research-os/kit-templates",
            "/research-os/data-contexts",
            "/research-os/under-contextualized-files",
            "/research-os/experiments",
            "/research-os/samples",
            "/research-os/data-files",
            "/research-os/conclusions",
            "/research-os/decisions",
            "/research-os/failures",
            "/research-os/memory/review-queue",
            "/research-os/protocols",
            "/research-os/conflicts",
            "/research-os/reports",
            "/research-os/claims",
        ]:
            with self.subTest(path=path):
                status, payload = self._request("GET", path)
                self.assertEqual(status, 400)
                self.assertIn("project_id is required", payload["error"])

    def test_detail_routes_require_matching_project_id(self) -> None:
        self._request("POST", "/research-os/projects", {"id": "status-a", "title": "Status A"})
        self._request("POST", "/research-os/projects", {"id": "status-b", "title": "Status B"})
        _, created_file = self._request(
            "POST",
            "/research-os/files",
            {"project_id": "status-a", "filename": "private.csv", "content": "a,b\n1,2"},
        )
        file_id = created_file["file"]["id"]
        skill_run = api.research_os.start_service_skill_run(
            self.agent_root,
            "project_status_test",
            "Project Status Test",
            "status-a",
            {"project_id": "status-a"},
        )
        literature_task = api.research_os.create_literature_search_task(
            self.agent_root,
            {"project_id": "status-a", "query": "private topic", "provider": "manual"},
        )["task"]
        protocol = api.research_os.store_protocol(
            self.agent_root,
            {"project_id": "status-a", "title": "Private protocol", "protocol_type": "qPCR", "steps": []},
        )
        _, created_claim = self._request(
            "POST",
            "/research-os/claims",
            {"project_id": "status-a", "claim_text": "Private claim", "claim_type": "hypothesis"},
        )
        claim_id = created_claim["claim"]["id"]

        detail_paths = [
            f"/research-os/files/{file_id}",
            f"/research-os/files/{file_id}/samples",
            f"/research-os/skill-runs/{skill_run['id']}",
            f"/research-os/literature/search-tasks/{literature_task['id']}",
            f"/research-os/literature/search-tasks/{literature_task['id']}/progress",
            f"/research-os/protocols/{protocol['id']}",
            f"/research-os/claims/{claim_id}",
        ]
        for path in detail_paths:
            with self.subTest(path=path, case="missing"):
                status, payload = self._request("GET", path)
                self.assertEqual(status, 400)
                self.assertIn("project_id is required", payload["error"])
            with self.subTest(path=path, case="wrong-project"):
                status, payload = self._request("GET", f"{path}?project_id=status-b")
                self.assertEqual(status, 404)
                self.assertIn("not found", payload["error"])
            with self.subTest(path=path, case="matching-project"):
                status, _ = self._request("GET", f"{path}?project_id=status-a")
                self.assertEqual(status, 200)

    def test_reference_mutations_require_matching_project_id(self) -> None:
        self._request("POST", "/research-os/projects", {"id": "status-a", "title": "Status A"})
        self._request("POST", "/research-os/projects", {"id": "status-b", "title": "Status B"})
        _, created = self._request(
            "POST",
            "/research-os/references",
            {"project_id": "status-a", "title": "Private reference"},
        )
        reference_id = created["reference"]["id"]
        path = f"/research-os/references/{reference_id}/tag"

        status, payload = self._request("POST", path, {"tag": "private"})
        self.assertEqual(status, 400)
        self.assertIn("project_id is required", payload["error"])

        status, payload = self._request("POST", path, {"project_id": "status-b", "tag": "private"})
        self.assertEqual(status, 404)
        self.assertIn("not found", payload["error"])

        status, payload = self._request("POST", path, {"project_id": "status-a", "tag": "private"})
        self.assertEqual(status, 200)
        self.assertIn("private", payload["reference"]["tags"])

    def test_workflow_run_requires_matching_project_id(self) -> None:
        self._request("POST", "/research-os/projects", {"id": "status-a", "title": "Status A"})
        self._request("POST", "/research-os/projects", {"id": "status-b", "title": "Status B"})
        _, created = self._request(
            "POST",
            "/research-os/workflows",
            {"project_id": "status-a", "template_key": "natural_language_command_to_workflow"},
        )
        workflow_id = created["workflow"]["id"]
        path = f"/research-os/workflows/{workflow_id}/run"

        status, payload = self._request("POST", path, {})
        self.assertEqual(status, 400)
        self.assertIn("project_id is required", payload["error"])

        status, payload = self._request("POST", path, {"project_id": "status-b"})
        self.assertEqual(status, 404)
        self.assertIn("not found", payload["error"])

        status, _ = self._request("POST", path, {"project_id": "status-a"})
        self.assertEqual(status, 200)

    def test_mutations_reject_unknown_project_id_without_creating_orphan_workspace(self) -> None:
        for path, payload in [
            ("/research-os/files", {"project_id": "missing-project", "filename": "orphan.txt", "content": "no"}),
            ("/research-os/workflows", {"project_id": "missing-project", "template_key": "natural_language_command_to_workflow"}),
            ("/research-os/references", {"project_id": "missing-project", "title": "Orphan reference"}),
        ]:
            with self.subTest(path=path):
                status, response = self._request("POST", path, payload)
                self.assertEqual(status, 404)
                self.assertIn("project not found", response["error"])
        self.assertFalse((self.agent_root / "projects" / "missing-project").exists())

    def test_task_detail_run_and_cancel_require_matching_project_id(self) -> None:
        self._request("POST", "/research-os/projects", {"id": "status-a", "title": "Status A"})
        self._request("POST", "/research-os/projects", {"id": "status-b", "title": "Status B"})
        _, created = self._request(
            "POST",
            "/research-os/tasks",
            {"project_id": "status-a", "task_type": "kb_summary"},
        )
        task_id = created["task"]["task_id"]

        status, payload = self._request("GET", f"/research-os/tasks/{task_id}")
        self.assertEqual(status, 400)
        self.assertIn("project_id is required", payload["error"])
        status, payload = self._request("GET", f"/research-os/tasks/{task_id}?project_id=status-b")
        self.assertEqual(status, 404)
        self.assertIn("not found", payload["error"])
        status, _ = self._request("GET", f"/research-os/tasks/{task_id}?project_id=status-a")
        self.assertEqual(status, 200)

        for action in ["run", "cancel"]:
            with self.subTest(action=action, case="missing"):
                status, payload = self._request("POST", f"/research-os/tasks/{task_id}/{action}", {})
                self.assertEqual(status, 400)
                self.assertIn("project_id is required", payload["error"])
            with self.subTest(action=action, case="wrong-project"):
                status, payload = self._request("POST", f"/research-os/tasks/{task_id}/{action}", {"project_id": "status-b"})
                self.assertEqual(status, 404)
                self.assertIn("not found", payload["error"])

    def test_project_record_mutations_require_matching_project_id(self) -> None:
        self._request("POST", "/research-os/projects", {"id": "status-a", "title": "Status A"})
        self._request("POST", "/research-os/projects", {"id": "status-b", "title": "Status B"})
        _, created_file = self._request(
            "POST",
            "/research-os/files",
            {"project_id": "status-a", "filename": "context.csv", "content": "sample_id,value\nS001,1"},
        )
        file_id = created_file["file"]["id"]
        _, file_detail = self._request("GET", f"/research-os/files/{file_id}?project_id=status-a")
        context_id = file_detail["file"]["data_context"]["id"]
        _, created_reference = self._request(
            "POST",
            "/research-os/references",
            {"project_id": "status-a", "title": "Scoped evidence"},
        )
        reference_id = created_reference["reference"]["id"]
        _, created_claim = self._request(
            "POST",
            "/research-os/claims",
            {"project_id": "status-a", "claim_text": "Scoped claim", "claim_type": "hypothesis"},
        )
        claim_id = created_claim["claim"]["id"]
        protocol = api.research_os.store_protocol(
            self.agent_root,
            {"project_id": "status-a", "title": "Scoped protocol", "protocol_type": "qPCR", "steps": []},
        )

        evidence_path = f"/research-os/evidence/reference:{reference_id}"
        for path in [evidence_path, f"{evidence_path}/mark-reviewed"]:
            method = "GET" if path == evidence_path else "POST"
            with self.subTest(path=path, case="missing"):
                status, payload = self._request(method, path, {} if method == "POST" else None)
                self.assertEqual(status, 400)
                self.assertIn("project_id is required", payload["error"])
            with self.subTest(path=path, case="wrong-project"):
                suffix = "?project_id=status-b" if method == "GET" else ""
                status, payload = self._request(method, f"{path}{suffix}", {"project_id": "status-b"} if method == "POST" else None)
                self.assertEqual(status, 404)
                self.assertIn("not found", payload["error"])

        status, _ = self._request("GET", f"{evidence_path}?project_id=status-a")
        self.assertEqual(status, 200)
        status, _ = self._request("POST", f"{evidence_path}/mark-reviewed", {"project_id": "status-a"})
        self.assertEqual(status, 200)

        for method, path, payload in [
            ("POST", f"/research-os/claims/{claim_id}/needs-more-evidence", {"reason": "Need validation"}),
            ("PUT", f"/research-os/data-contexts/{context_id}", {"experiment_name": "Scoped run"}),
        ]:
            with self.subTest(path=path, case="missing"):
                status, response = self._request(method, path, payload)
                self.assertEqual(status, 400)
                self.assertIn("project_id is required", response["error"])
            with self.subTest(path=path, case="wrong-project"):
                status, response = self._request(method, path, {**payload, "project_id": "status-b"})
                self.assertEqual(status, 404)
                self.assertIn("not found", response["error"])

        for path, payload in [
            ("/research-os/extraction", {"file_id": file_id}),
            ("/research-os/protocol-execution-package", {"protocol_id": protocol["id"]}),
            ("/research-os/kit-templates/parse", {"source_file_id": file_id}),
        ]:
            with self.subTest(path=path, case="missing"):
                status, response = self._request("POST", path, payload)
                self.assertEqual(status, 400)
                self.assertIn("project_id is required", response["error"])
            with self.subTest(path=path, case="wrong-project"):
                status, response = self._request("POST", path, {**payload, "project_id": "status-b"})
                self.assertEqual(status, 404)
                self.assertIn("not found", response["error"])
            with self.subTest(path=path, case="matching-project"):
                status, _ = self._request("POST", path, {**payload, "project_id": "status-a"})
                self.assertEqual(status, 200)

    def test_purge_route_requires_confirm_true(self) -> None:
        _, created = self._request("POST", "/research-os/projects", {"id": "purge-a", "title": "Purge A"})
        project = created["project"]

        _, refused = self._request("POST", f"/research-os/projects/{project['id']}/purge", {"confirmation": "CONFIRM PURGE Purge A"})
        self.assertFalse(refused["executed"])
        self.assertEqual(refused["reason"], "confirm_true_required")

        _, purged = self._request(
            "POST",
            f"/research-os/projects/{project['id']}/purge",
            {"confirmation": "CONFIRM PURGE Purge A", "confirm": True},
        )
        self.assertTrue(purged["executed"])


if __name__ == "__main__":
    unittest.main()
