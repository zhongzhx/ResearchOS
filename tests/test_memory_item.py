import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.memory.memory_item import (
    archive_memory_item,
    create_memory_item,
    mark_superseded,
    memory_item_from_dict,
    memory_item_to_dict,
    update_access_stats,
    validate_memory_item,
)
from backend.researchos.memory.semantic.semantic_memory_store import create_semantic_memory_item, load_semantic_memory


class MemoryItemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_item_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_high_confidence_without_provenance_is_downgraded(self) -> None:
        item = create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="Claim", content="X", confidence="high")

        self.assertEqual(item.confidence, "medium")
        self.assertIn("confidence_downgraded_missing_provenance", item.safety_tags)

    def test_hypothesis_defaults_to_low_confidence(self) -> None:
        item = create_memory_item(project_id="p1", memory_layer="semantic", memory_type="hypothesis", title="Hyp", content="Maybe X")

        self.assertEqual(item.confidence, "low")
        self.assertTrue(validate_memory_item(item)["valid"])

    def test_round_trip_and_access_stats(self) -> None:
        item = create_memory_item(project_id="p1", memory_layer="semantic", memory_type="project_fact", title="Fact", content="A", source_ids=["s1"])
        created = create_semantic_memory_item(item)
        update_access_stats(created["memory_id"])
        loaded = load_semantic_memory(created["memory_id"])

        self.assertEqual(memory_item_from_dict(memory_item_to_dict(item)).title, "Fact")
        self.assertEqual(loaded["retrieval_count"], 1)
        self.assertTrue(loaded["last_accessed_at"])

    def test_supersede_and_archive_do_not_delete(self) -> None:
        a = create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="Old", content="Old", source_ids=["s1"]))
        b = create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="New", content="New", source_ids=["s2"]))

        superseded = mark_superseded(a["memory_id"], b["memory_id"], "new evidence")
        archived = archive_memory_item(a["memory_id"], "cold memory")

        self.assertEqual(superseded["status"], "superseded")
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(load_semantic_memory(a["memory_id"])["status"], "archived")


if __name__ == "__main__":
    unittest.main()
