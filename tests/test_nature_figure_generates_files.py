import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from backend.researchos.execution.coding_runtime import CodingRuntimeService
from backend.researchos.workspace.file_artifact_registry import FileArtifactRegistry


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class NatureFigureGeneratesFilesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_figure_runtime_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"id": "figure-project", "title": "Figure Project"})
        self.registry = FileArtifactRegistry(self.agent_root)
        self.runtime = CodingRuntimeService(self.agent_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_basic_stats_plot_generates_svg_png_spec_code_summary_and_qa(self) -> None:
        source = self.registry.register_content(
            project_id=self.project["id"],
            source_type="upload",
            display_name="values.csv",
            content="group,value\ncontrol,1\ncontrol,2\ntreated,4\ntreated,6\n",
        )

        result = self.runtime.execute_template(
            self.project["id"],
            "basic_stats_plot",
            {"project_id": self.project["id"], "artifact_id": source["artifact_id"], "x": "group", "y": "value"},
        )

        self.assertTrue(result["ok"], result)
        names = {item["display_name"] for item in result["artifacts"]}
        self.assertTrue({"summary.csv", "figure.svg", "figure.png", "figure_code.py", "figure_spec.md", "qa_report.md"}.issubset(names))
        for artifact in result["artifacts"]:
            self.assertTrue(Path(artifact["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
