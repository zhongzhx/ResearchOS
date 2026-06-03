import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from backend.researchos.integration.workflow_execution_service import WorkflowExecutionService


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class NoFakeSuccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_no_fake_success_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"id": "no-fake", "title": "No Fake"})

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_not_connected_workflow_has_no_run_or_artifacts(self) -> None:
        result = WorkflowExecutionService(self.agent_root).execute(
            project_id=self.project["id"],
            intent="literature_harvest_and_kb",
            params={"keywords": ["test"]},
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "not_connected")
        self.assertFalse(result["run_id"])
        self.assertEqual(result["artifacts"], [])


if __name__ == "__main__":
    unittest.main()
