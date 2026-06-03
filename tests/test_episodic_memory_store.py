import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.memory.episodic.episodic_memory_store import (
    create_episode_from_skillrun,
    create_episode_from_task,
    link_episode_to_memory_items,
    list_recent_episodes,
    search_episodes,
)


class EpisodicMemoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_episode_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")
        os.environ["RESEARCHOS_TASKS_ROOT"] = str(self.tmp / "tasks")
        task_dir = self.tmp / "tasks" / "t1"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(json.dumps({"task_id": "t1", "project_id": "p1", "user_query": "analyze", "status": "failed"}), encoding="utf-8")
        (task_dir / "execution_result.json").write_text(json.dumps({"task_id": "t1", "skillrun_id": "sr1", "status": "failed", "summary": "parse failed", "errors": ["bad csv"]}), encoding="utf-8")
        (task_dir / "validation_report.json").write_text(json.dumps({"safe_to_promote": False}), encoding="utf-8")

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        os.environ.pop("RESEARCHOS_TASKS_ROOT", None)
        os.environ.pop("RESEARCHOS_AGENT_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_failed_task_generates_failed_episode(self) -> None:
        episode = create_episode_from_task("t1")

        self.assertEqual(episode["outcome"], "failed")
        self.assertIn("bad csv", str(episode["unresolved_items"]))
        self.assertEqual(list_recent_episodes("p1")[0]["task_id"], "t1")

    def test_skillrun_payload_generates_episode_and_searches(self) -> None:
        run = {"id": "sr2", "project_id": "p1", "skill_id": "skill-a", "skill_name": "Skill A", "status": "completed", "input_payload": {"task_id": "t2", "user_query": "write report"}, "output_payload": {"summary": "report ready"}}
        episode = create_episode_from_skillrun("sr2", skillrun=run)
        linked = link_episode_to_memory_items(episode["episode_id"], ["mem1"], project_id="p1")

        self.assertEqual(linked["memory_ids"], ["mem1"])
        self.assertTrue(search_episodes("p1", "report"))


if __name__ == "__main__":
    unittest.main()
