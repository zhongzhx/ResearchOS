import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.memory.events.event_store import append_event, export_events, list_events, load_event, replay_events
from backend.researchos.memory.memory_event import create_memory_event


class EventStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_store_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_append_load_list_replay_and_export(self) -> None:
        event = create_memory_event(event_type="task_created", project_id="p1", task_id="t1", source_type="task", payload={"secret": "sk-test123"})
        written = append_event(event)

        self.assertEqual(load_event(written["event_id"])["task_id"], "t1")
        self.assertEqual(len(list_events(project_id="p1", task_id="t1", event_type="task_created")), 1)
        self.assertEqual(len(replay_events("p1")), 1)
        self.assertNotIn("sk-test123", (self.tmp / "memoryos" / "events" / "p1" / "events.jsonl").read_text(encoding="utf-8"))

        exported = export_events("p1", str(self.tmp / "export.json"))
        self.assertEqual(exported["count"], 1)


if __name__ == "__main__":
    unittest.main()
