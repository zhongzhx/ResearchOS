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


class DataProfileWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_data_profile_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"id": "profile-project", "title": "Profile Project"})
        self.registry = FileArtifactRegistry(self.agent_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scientific_data_analysis_profiles_registered_csv(self) -> None:
        source = self.registry.register_content(
            project_id=self.project["id"],
            source_type="upload",
            display_name="minimal.csv",
            content="sample,value\nA,1\nB,\n",
        )

        result = WorkflowExecutionService(self.agent_root).execute(
            project_id=self.project["id"],
            intent="scientific_data_analysis",
            params={"artifact_id": source["artifact_id"]},
        )

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["run_id"])
        self.assertTrue({"data_profile.md", "columns.csv", "missing_values.csv"}.issubset({item["display_name"] for item in result["artifacts"]}))

    def test_scientific_data_analysis_can_run_qpcr_template(self) -> None:
        source = self.registry.register_content(
            project_id=self.project["id"],
            source_type="upload",
            display_name="qpcr.csv",
            content="sample,group,target_cq,reference_cq\nctrl,control,22,18\ntreated,treatment,20,18\n",
        )

        result = WorkflowExecutionService(self.agent_root).execute(
            project_id=self.project["id"],
            intent="scientific_data_analysis",
            params={"artifact_id": source["artifact_id"], "runtime_template": "qpcr_template", "control_group": "control"},
        )

        self.assertTrue(result["ok"], result)
        self.assertTrue({"qpcr_delta_ct.csv", "qpcr_expression.svg", "qpcr_expression.png"}.issubset({item["display_name"] for item in result["artifacts"]}))


if __name__ == "__main__":
    unittest.main()
