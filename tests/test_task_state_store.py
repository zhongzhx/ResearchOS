import json
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.tasks.task_state_store import ResearchTaskStateStore


class TaskStateStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="task_state_store_"))
        self.store = ResearchTaskStateStore(self.tmp / "research_tasks")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_task_makes_directory_and_events(self) -> None:
        task = self.store.create_task("project_1", "run task", task_id="task_store")

        task_dir = self.store.task_dir(task.task_id)
        self.assertTrue(task_dir.exists())
        self.assertTrue((task_dir / "task.json").exists())
        self.assertTrue((task_dir / "events.jsonl").exists())
        self.assertEqual(json.loads((task_dir / "task.json").read_text(encoding="utf-8"))["status"], "created")

    def test_load_task_roundtrip(self) -> None:
        task = self.store.create_task("project_1", "run task", task_id="task_roundtrip")
        self.store.write_goal(task, {"research_objective": "run task"})

        loaded = self.store.load_task(task.task_id)

        self.assertEqual(loaded.task_id, task.task_id)
        self.assertEqual(loaded.goal["research_objective"], "run task")


if __name__ == "__main__":
    unittest.main()
