import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.researchos.execution.coding_runtime import CodingRuntimeService


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class PptGenerationArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_ppt_runtime_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"id": "ppt-project", "title": "PPT Project"})

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_outline_generates_real_pptx_registered_in_project_library(self) -> None:
        runtime = CodingRuntimeService(self.agent_root)
        result = runtime.execute_template(
            self.project["id"],
            "ppt_from_outline",
            {"outline": [{"title": "Journal Club", "body": "Paper overview"}, {"title": "Methods", "body": "Study design"}]},
        )

        self.assertTrue(result["ok"], result)
        ppt = next(item for item in result["artifacts"] if item["display_name"] == "journal_club.pptx")
        self.assertEqual(ppt["preview_type"], "pptx")
        self.assertTrue(zipfile.is_zipfile(ppt["path"]))
        self.assertIn(ppt["artifact_id"], {row["artifact_id"] for row in ros.list_registered_artifacts(self.agent_root, self.project["id"])})


if __name__ == "__main__":
    unittest.main()
