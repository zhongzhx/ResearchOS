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


class ResearchOSProjectArtifactArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_artifact_archive_"))
        self.agent_root = self.tmp / "agent_data"
        self.project_a = ros.create_project(self.agent_root, {"id": "artifact-a", "title": "Artifact A"})
        self.project_b = ros.create_project(self.agent_root, {"id": "artifact-b", "title": "Artifact B"})

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_archives_research_deliverables_by_kind(self) -> None:
        cases = [
            ("analysis.md", "# Analysis\n", "markdown"),
            ("figure.svg", "<svg xmlns='http://www.w3.org/2000/svg'></svg>", "figures"),
            ("figure.png", b"\x89PNG\r\n\x1a\nunit", "figures"),
            ("journal-club.pptx", b"PK\x03\x04unit-pptx", "presentations"),
        ]

        archived = [
            ros.archive_project_artifact(
                self.agent_root,
                {
                    "project_id": self.project_a["id"],
                    "filename": filename,
                    "content": content,
                    "artifact_type": kind,
                    "title": filename,
                },
            )
            for filename, content, kind in cases
        ]

        for artifact, (_, content, kind) in zip(archived, cases, strict=True):
            path = Path(artifact["path"])
            self.assertTrue(path.is_file())
            self.assertEqual(path.parent.name, kind)
            expected = content if isinstance(content, bytes) else content.encode("utf-8")
            self.assertEqual(path.read_bytes(), expected)

    def test_listing_is_project_scoped(self) -> None:
        artifact_a = ros.archive_project_artifact(
            self.agent_root,
            {"project_id": self.project_a["id"], "filename": "a.md", "content": "alpha", "artifact_type": "markdown"},
        )
        ros.archive_project_artifact(
            self.agent_root,
            {"project_id": self.project_b["id"], "filename": "b.md", "content": "beta", "artifact_type": "markdown"},
        )

        rows = ros.list_project_artifacts(self.agent_root, self.project_a["id"])

        self.assertEqual({item["artifact_id"] for item in rows}, {artifact_a["artifact_id"]})
        self.assertEqual({item["project_id"] for item in rows}, {self.project_a["id"]})
        with self.assertRaisesRegex(ValueError, "project_id is required"):
            ros.list_project_artifacts(self.agent_root)


if __name__ == "__main__":
    unittest.main()
