import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from backend.researchos.execution.coding_runtime import CodingRuntimeService


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class CodingRuntimeArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_coding_artifacts_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"id": "coding-artifacts", "title": "Coding Artifacts"})
        self.runtime = CodingRuntimeService(self.agent_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_markdown_report_registers_real_output(self) -> None:
        result = self.runtime.execute_template(
            self.project["id"],
            "markdown_report",
            {"title": "Weekly Notes", "sections": {"Progress": "Completed profiling.", "Next": "Plot results."}},
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["run_id"])
        self.assertEqual(len(result["artifacts"]), 1)
        artifact = result["artifacts"][0]
        self.assertEqual(artifact["preview_type"], "markdown")
        self.assertTrue(Path(artifact["path"]).is_file())
        self.assertIn("Completed profiling.", Path(artifact["path"]).read_text(encoding="utf-8"))
        self.assertEqual({row["artifact_id"] for row in ros.list_project_artifacts(self.agent_root, self.project["id"])}, {artifact["artifact_id"]})

    def test_qpcr_template_generates_delta_delta_ct_and_figure_draft(self) -> None:
        uploaded = ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "filename": "qpcr.csv",
                "content": "sample,group,target_cq,reference_cq\nctrl-1,control,22,18\ntreat-1,treatment,20,18\n",
            },
        )

        result = self.runtime.execute_template(
            self.project["id"],
            "qpcr_template",
            {"project_id": self.project["id"], "artifact_id": uploaded["artifact_id"], "control_group": "control"},
        )

        self.assertTrue(result["ok"], result)
        names = {item["display_name"] for item in result["artifacts"]}
        self.assertEqual(names, {"qpcr_delta_ct.csv", "qpcr_statistics_advice.md", "qpcr_expression.svg", "qpcr_expression.png"})
        table = next(item for item in result["artifacts"] if item["display_name"] == "qpcr_delta_ct.csv")
        csv_text = Path(table["path"]).read_text(encoding="utf-8")
        self.assertIn("delta_delta_ct", csv_text)
        self.assertIn("relative_expression", csv_text)


if __name__ == "__main__":
    unittest.main()
