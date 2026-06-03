import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


REQUIRED_DIRS = [
    "inbox",
    "papers",
    "papers/pdfs",
    "papers/manual_queue",
    "kb",
    "rag",
    "chats",
    "workflows",
    "runs",
    "artifacts",
    "artifacts/markdown",
    "artifacts/pptx",
    "artifacts/figures",
    "artifacts/tables",
    "artifacts/data",
    "logs",
    "tmp",
    "manifests",
]

REQUIRED_MANIFEST_FIELDS = {
    "display_name",
    "project_id",
    "created_at",
    "updated_at",
    "root_path",
    "kb_path",
    "rag_path",
    "artifact_path",
    "file_count",
    "reference_count",
    "kb_entry_count",
    "rag_chunk_count",
    "workflow_run_count",
    "last_activity_at",
}


class ProjectWorkspaceIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_workspace_isolation_"))
        self.agent_root = self.tmp / "agent_root"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_projects_use_project_id_roots_and_complete_layout(self) -> None:
        project_a = ros.create_project(self.agent_root, {"id": "project-a", "title": "Shared Name"})
        project_b = ros.create_project(self.agent_root, {"id": "project-b", "title": "Shared Name"})

        for project in [project_a, project_b]:
            root = self.agent_root / "projects" / project["id"]
            self.assertEqual(Path(project["root_dir"]), root)
            self.assertEqual(Path(project["uploads_dir"]), root / "inbox")
            self.assertEqual(Path(project["pdf_dir"]), root / "papers" / "pdfs")
            self.assertEqual(Path(project["kb_dir"]), root / "kb")
            for relative in REQUIRED_DIRS:
                with self.subTest(project=project["id"], relative=relative):
                    self.assertTrue((root / relative).is_dir())
            self.assertTrue((root / "project_manifest.json").is_file())

        self.assertNotEqual(project_a["root_dir"], project_b["root_dir"])

    def test_manifest_exposes_required_auditable_fields(self) -> None:
        project = ros.create_project(self.agent_root, {"id": "manifest-project", "title": "Manifest Project"})
        ros.register_file(self.agent_root, {"project_id": project["id"], "filename": "input.csv", "content": "group,value\nA,1"})
        ros.archive_project_artifact(
            self.agent_root,
            {"project_id": project["id"], "filename": "summary.md", "content": "# Summary", "artifact_type": "markdown"},
        )

        status = ros.get_project_status(self.agent_root, project["id"])
        manifest_path = Path(status["manifest_path"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest_path, self.agent_root / "projects" / project["id"] / "project_manifest.json")
        self.assertTrue(REQUIRED_MANIFEST_FIELDS.issubset(manifest))
        self.assertEqual(manifest["display_name"], "Manifest Project")
        self.assertEqual(manifest["project_id"], project["id"])
        self.assertEqual(manifest["root_path"], project["root_dir"])
        self.assertGreaterEqual(manifest["file_count"], 1)
        self.assertGreaterEqual(status["artifact_count"], 1)

    def test_files_and_artifacts_are_isolated_between_projects(self) -> None:
        project_a = ros.create_project(self.agent_root, {"id": "alpha", "title": "Alpha"})
        project_b = ros.create_project(self.agent_root, {"id": "beta", "title": "Beta"})
        ros.register_file(self.agent_root, {"project_id": project_a["id"], "filename": "alpha.csv", "content": "alpha"})
        ros.register_file(self.agent_root, {"project_id": project_b["id"], "filename": "beta.csv", "content": "beta"})
        ros.archive_project_artifact(self.agent_root, {"project_id": project_a["id"], "filename": "alpha.md", "content": "alpha"})
        ros.archive_project_artifact(self.agent_root, {"project_id": project_b["id"], "filename": "beta.md", "content": "beta"})

        self.assertEqual({row["original_filename"] for row in ros.list_files(self.agent_root, project_a["id"])}, {"alpha.csv"})
        self.assertEqual({row["original_filename"] for row in ros.list_files(self.agent_root, project_b["id"])}, {"beta.csv"})
        self.assertEqual({row["title"] for row in ros.list_project_artifacts(self.agent_root, project_a["id"]) if row["type"] == "markdown"}, {"alpha.md"})
        self.assertEqual({row["title"] for row in ros.list_project_artifacts(self.agent_root, project_b["id"]) if row["type"] == "markdown"}, {"beta.md"})


if __name__ == "__main__":
    unittest.main()
