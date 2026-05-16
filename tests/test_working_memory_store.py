import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.memory.working.working_memory_store import (
    append_recent_message,
    clear_working_memory,
    compact_working_memory,
    get_working_memory,
    set_current_task,
    update_working_memory,
)


class WorkingMemoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_working_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_recent_messages_are_fifo_and_redacted(self) -> None:
        for i in range(25):
            append_recent_message("c1", "user", f"message {i} token=abc{i}", {"project_id": "p1"})

        memory = get_working_memory("c1", "p1")
        self.assertEqual(len(memory["recent_messages"]), 20)
        self.assertIn("message 5", memory["recent_messages"][0]["content"])
        self.assertNotIn("abc24", str(memory))

    def test_current_task_patch_compact_and_clear(self) -> None:
        update_working_memory("c1", "p1", {"current_goal": "Do X", "active_constraints": ["no secrets"]})
        set_current_task("c1", "t1", project_id="p1")
        compact_working_memory("c1", project_id="p1", max_items=5)
        memory = get_working_memory("c1", "p1")

        self.assertEqual(memory["current_task_id"], "t1")
        self.assertEqual(memory["current_goal"], "Do X")
        cleared = clear_working_memory("c1", project_id="p1", reason="done")
        self.assertEqual(cleared["recent_messages"], [])


if __name__ == "__main__":
    unittest.main()
