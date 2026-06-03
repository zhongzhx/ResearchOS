import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.researchos.workspace.file_artifact_registry import FileArtifactRegistry


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class KnowledgeBaseIngestStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_kb_ingest_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"id": "kb-project", "title": "KB Project"})
        self.registry = FileArtifactRegistry(self.agent_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pdf_is_not_indexed_until_ingest_status_is_updated(self) -> None:
        artifact = self.registry.register_content(
            project_id=self.project["id"],
            source_type="literature_pdf",
            display_name="paper.pdf",
            content=b"%PDF-1.4\n",
        )
        self.assertEqual(artifact["status"], "registered")
        self.assertEqual(artifact["ingest_status"], "registered")
        self.assertNotEqual(artifact["kb_status"], "indexed")

        ingesting = self.registry.update_ingest_status(self.project["id"], artifact["artifact_id"], "ingesting")
        indexed = self.registry.update_ingest_status(
            self.project["id"], artifact["artifact_id"], "indexed", kb_status="indexed", rag_status="indexed"
        )

        self.assertEqual(ingesting["status"], "ingesting")
        self.assertEqual(indexed["status"], "indexed")
        self.assertEqual(indexed["kb_status"], "indexed")
        self.assertEqual(indexed["rag_status"], "indexed")

    def test_kb_build_marks_artifact_failed_when_ingest_raises(self) -> None:
        artifact = self.registry.register_content(
            project_id=self.project["id"],
            source_type="literature_pdf",
            display_name="broken.pdf",
            content=b"%PDF-1.4\n",
        )

        with patch.object(ros, "analyze_references_with_article_keyword_skill", side_effect=RuntimeError("parser failed")):
            with self.assertRaisesRegex(RuntimeError, "parser failed"):
                ros.build_project_research_kb(
                    self.agent_root,
                    {"project_id": self.project["id"], "artifact_ids": [artifact["artifact_id"]]},
                )

        failed = self.registry.get(self.project["id"], artifact["artifact_id"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["ingest_status"], "failed")


if __name__ == "__main__":
    unittest.main()
