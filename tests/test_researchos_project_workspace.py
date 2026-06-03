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


class ResearchOSProjectWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_project_workspace_"))
        self.agent_root = self.tmp / "agent_data"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_same_named_projects_receive_distinct_complete_workspaces(self) -> None:
        first = ros.create_project(self.agent_root, {"id": "project-alpha", "title": "Natural Products"})
        second = ros.create_project(self.agent_root, {"id": "project-beta", "title": "Natural Products"})

        self.assertNotEqual(first["root_dir"], second["root_dir"])
        for project in [first, second]:
            root = Path(project["root_dir"])
            self.assertTrue(root.is_dir())
            for relative in [
                "uploads",
                "papers",
                "knowledge",
                "artifacts/markdown",
                "artifacts/figures",
                "artifacts/presentations",
                "artifacts/data",
                "artifacts/other",
                "runs",
            ]:
                self.assertTrue((root / relative).is_dir(), relative)
            self.assertTrue((root / "workspace.json").is_file())

    def test_workspace_state_exposes_manifest_kb_and_rag_scope(self) -> None:
        project = ros.create_project(self.agent_root, {"id": "project-kb", "title": "Macrophage KB"})
        reference = ros.import_reference(
            self.agent_root,
            {
                "project_id": project["id"],
                "title": "Macrophage reference",
                "abstract": "Macrophage cytokine evidence.",
                "full_text": "Macrophage cytokine evidence from a local paper.",
                "source_provider": "unit",
                "access_status": "downloaded",
            },
        )
        ros.build_project_research_kb(
            self.agent_root,
            {"project_id": project["id"], "reference_ids": [reference["id"]], "include_article_analysis": False},
        )

        state = ros.workspace_state(self.agent_root, project["id"])
        workspace = state["project_workspace"]

        self.assertEqual(workspace["project_id"], project["id"])
        self.assertEqual(workspace["rag"]["default_scope"], "current_project")
        self.assertTrue(workspace["rag"]["cross_project_requires_explicit_opt_in"])
        self.assertTrue(workspace["kb"]["ready"])
        self.assertGreaterEqual(workspace["kb"]["entries_count"], 1)
        self.assertEqual(Path(workspace["paths"]["papers_dir"]), Path(project["pdf_dir"]))
        self.assertEqual(Path(workspace["paths"]["knowledge_dir"]), Path(project["kb_dir"]))

        saved = json.loads(Path(workspace["manifest_path"]).read_text(encoding="utf-8"))
        self.assertEqual(saved["project_id"], project["id"])
        self.assertEqual(saved["rag"]["default_scope"], "current_project")
        self.assertTrue(saved["kb"]["ready"])


if __name__ == "__main__":
    unittest.main()
