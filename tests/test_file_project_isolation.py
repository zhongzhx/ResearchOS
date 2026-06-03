import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from backend.researchos.workspace.file_artifact_registry import FileArtifactRegistry


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class FileProjectIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_file_isolation_"))
        self.agent_root = self.tmp / "agent_data"
        self.project_a = ros.create_project(self.agent_root, {"id": "file-a", "title": "File A"})
        self.project_b = ros.create_project(self.agent_root, {"id": "file-b", "title": "File B"})
        self.registry = FileArtifactRegistry(self.agent_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_two_projects_can_register_same_filename_without_leaking(self) -> None:
        artifact_a = self.registry.register_content(
            project_id=self.project_a["id"], source_type="upload", display_name="shared.csv", content="a,1\n"
        )
        artifact_b = self.registry.register_content(
            project_id=self.project_b["id"], source_type="upload", display_name="shared.csv", content="b,2\n"
        )

        self.assertNotEqual(artifact_a["absolute_path"], artifact_b["absolute_path"])
        self.assertEqual({row["artifact_id"] for row in self.registry.list(self.project_a["id"])}, {artifact_a["artifact_id"]})
        self.assertEqual({row["artifact_id"] for row in self.registry.list(self.project_b["id"])}, {artifact_b["artifact_id"]})
        with self.assertRaisesRegex(KeyError, "artifact not found"):
            self.registry.get(self.project_b["id"], artifact_a["artifact_id"])

    def test_path_traversal_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "safe filename"):
            self.registry.register_content(
                project_id=self.project_a["id"],
                source_type="upload",
                display_name="../escape.csv",
                content="x,1\n",
            )

    def test_external_file_requires_explicit_upload_import(self) -> None:
        outside = self.tmp / "outside.csv"
        outside.write_text("x,1\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "project workspace"):
            self.registry.register_file(
                project_id=self.project_a["id"],
                source_type="upload",
                file_path=outside,
            )

        imported = ros.register_file_artifact(
            self.agent_root,
            {"project_id": self.project_a["id"], "source_type": "upload", "file_path": str(outside), "display_name": "imported.csv"},
            allow_external_source=True,
        )
        self.assertTrue(Path(imported["absolute_path"]).is_file())
        self.assertTrue(str(Path(imported["absolute_path"])).startswith(str(self.agent_root / "projects" / self.project_a["id"])))


if __name__ == "__main__":
    unittest.main()
