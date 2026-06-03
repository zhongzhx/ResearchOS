import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.workspace.file_artifact_registry import FileArtifactRegistry

import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class ArtifactRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_artifact_registry_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"id": "registry-project", "title": "Registry Project"})
        self.registry = FileArtifactRegistry(self.agent_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_same_hash_is_deduplicated_and_different_content_does_not_overwrite(self) -> None:
        first = self.registry.register_content(
            project_id=self.project["id"],
            source_type="upload",
            display_name="results.csv",
            content=b"group,value\ncontrol,1\n",
        )
        duplicate = self.registry.register_content(
            project_id=self.project["id"],
            source_type="upload",
            display_name="results.csv",
            content=b"group,value\ncontrol,1\n",
        )
        changed = self.registry.register_content(
            project_id=self.project["id"],
            source_type="upload",
            display_name="results.csv",
            content=b"group,value\ncontrol,2\n",
        )

        self.assertEqual(first["artifact_id"], duplicate["artifact_id"])
        self.assertNotEqual(first["artifact_id"], changed["artifact_id"])
        self.assertNotEqual(first["absolute_path"], changed["absolute_path"])
        self.assertEqual(Path(first["absolute_path"]).read_bytes(), b"group,value\ncontrol,1\n")
        self.assertEqual(Path(changed["absolute_path"]).read_bytes(), b"group,value\ncontrol,2\n")

    def test_soft_delete_keeps_file_until_physical_delete_requested(self) -> None:
        artifact = self.registry.register_content(
            project_id=self.project["id"],
            source_type="generated_markdown",
            display_name="summary.md",
            content="# Summary\n",
        )

        deleted = self.registry.delete(self.project["id"], artifact["artifact_id"])

        self.assertEqual(deleted["status"], "deleted")
        self.assertTrue(Path(artifact["absolute_path"]).is_file())
        self.assertEqual(self.registry.list(self.project["id"]), [])

        self.registry.delete(self.project["id"], artifact["artifact_id"], physical_delete=True)
        self.assertFalse(Path(artifact["absolute_path"]).exists())

    def test_open_info_returns_user_facing_preview_metadata(self) -> None:
        artifact = self.registry.register_content(
            project_id=self.project["id"],
            source_type="generated_markdown",
            display_name="report.md",
            content="# Report\n",
        )

        info = self.registry.open_info(self.project["id"], artifact["artifact_id"])

        self.assertEqual(info["display_name"], "report.md")
        self.assertEqual(info["preview_type"], "markdown")
        self.assertEqual(info["mime_type"], "text/markdown")
        self.assertIn("open_hint", info)


if __name__ == "__main__":
    unittest.main()
