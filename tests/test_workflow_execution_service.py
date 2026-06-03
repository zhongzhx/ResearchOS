import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from backend.researchos.integration.workflow_execution_service import WorkflowExecutionService
from backend.researchos.workspace.file_artifact_registry import FileArtifactRegistry


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class WorkflowExecutionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_workflow_service_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"id": "workflow-project", "title": "Workflow Project"})
        self.registry = FileArtifactRegistry(self.agent_root)
        self.service = WorkflowExecutionService(self.agent_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_four_required_nature_workflows_create_runs_and_registered_artifacts(self) -> None:
        table = self.registry.register_content(
            project_id=self.project["id"],
            source_type="upload",
            display_name="plot.csv",
            content="group,value\ncontrol,1\ntreated,2\n",
        )
        cases = [
            ("nature_figure_generation", {"artifact_id": table["artifact_id"], "x": "group", "y": "value"}),
            ("nature_paper_to_ppt", {"paper_text": "A supplied paper summary."}),
            ("nature_academic_polishing", {"text": "  The supplied abstract.  "}),
            ("nature_reviewer_response", {"reviewer_comments": "Please clarify the controls."}),
        ]

        for intent, params in cases:
            with self.subTest(intent=intent):
                result = self.service.execute(project_id=self.project["id"], intent=intent, params=params)
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["status"], "completed")
                self.assertTrue(result["run_id"])
                self.assertTrue(result["artifacts"])
                run = ros.get_skill_run(self.agent_root, result["run_id"], self.project["id"])
                self.assertEqual(run["status"], "completed")
                self.assertTrue(all(Path(item["path"]).is_file() for item in result["artifacts"]))

    def test_missing_file_is_honest(self) -> None:
        result = self.service.execute(project_id=self.project["id"], intent="nature_figure_generation", params={"x": "group", "y": "value"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "needs_file")
        self.assertFalse(result["run_id"])
        self.assertEqual(result["artifacts"], [])


if __name__ == "__main__":
    unittest.main()
