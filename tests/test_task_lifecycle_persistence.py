import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.agents.coordinator import AgentCoordinator


class TaskLifecyclePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_task_lifecycle_"))
        self.previous = {
            "RESEARCHOS_AGENT_ROOT": os.environ.get("RESEARCHOS_AGENT_ROOT"),
            "RESEARCHOS_TASKS_ROOT": os.environ.get("RESEARCHOS_TASKS_ROOT"),
        }
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.tmp / "agent_data")
        os.environ["RESEARCHOS_TASKS_ROOT"] = str(self.tmp / "data" / "research_tasks")

    def tearDown(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_full_cycle_persists_core_lifecycle_files(self) -> None:
        response = AgentCoordinator().run_full_cycle("summarize project status", project_id="p1")

        task_dir = Path(response["research_task_dir"])
        for filename in ["task.json", "goal.json", "plan.md", "contract.json", "execution_result.json", "artifacts.json", "validation_report.json", "memory_commit.json", "handoff.md"]:
            self.assertTrue((task_dir / filename).exists(), filename)


if __name__ == "__main__":
    unittest.main()
