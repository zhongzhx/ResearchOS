import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.memory.governance.archive_policy import archive_memory, list_archived_memories, restore_archived_memory
from backend.researchos.memory.governance.decay_policy import apply_forgetting_curve, compute_decay_score, mark_for_archive_if_cold, reinforce_on_retrieval
from backend.researchos.memory.memory_item import create_memory_item
from backend.researchos.memory.semantic.semantic_memory_store import create_semantic_memory_item, load_semantic_memory


class DecayPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_decay_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_decay_reinforce_and_archive_restore(self) -> None:
        item = create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="hypothesis", title="Cold", content="Maybe", confidence="low", importance_score=0.1))

        self.assertGreaterEqual(compute_decay_score(item), 0)
        apply_forgetting_curve("p1")
        reinforced = reinforce_on_retrieval(item["memory_id"])
        cold = mark_for_archive_if_cold(item["memory_id"])
        archived = archive_memory(item["memory_id"], "manual")
        restored = restore_archived_memory(item["memory_id"], "needed")

        self.assertGreaterEqual(reinforced["retrieval_count"], 1)
        self.assertIn(cold["status"], {"active", "needs_review", "archived"})
        self.assertTrue(list_archived_memories("p1"))
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(restored["status"], "active")
        self.assertEqual(load_semantic_memory(item["memory_id"])["status"], "active")


if __name__ == "__main__":
    unittest.main()
