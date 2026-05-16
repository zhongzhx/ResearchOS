import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.memory.governance.conflict_resolver import detect_conflicts, mark_conflict, resolve_conflict
from backend.researchos.memory.governance.memory_manager import ingest_memory_item, merge_similar_memories, reinforce_memory, run_memory_maintenance
from backend.researchos.memory.memory_item import create_memory_item


class MemoryGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_governance_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_conflict_detection_marks_needs_review(self) -> None:
        a = ingest_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="Claim", content="TLR4 increases IL6", source_ids=["s1"]))
        b = ingest_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="Claim", content="TLR4 decreases IL6", source_ids=["s2"]))

        conflicts = detect_conflicts("p1")
        marked = mark_conflict(a["memory_id"], b["memory_id"], "opposite direction")
        resolved = resolve_conflict(marked["conflict_id"], "needs validation")

        self.assertTrue(conflicts)
        self.assertEqual(marked["status"], "needs_review")
        self.assertEqual(resolved["resolution"], "needs validation")

    def test_merge_reinforce_and_maintenance(self) -> None:
        item = ingest_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="project_fact", title="Fact", content="Fact text", source_ids=["s1"]))

        reinforced = reinforce_memory(item["memory_id"], "user confirmed")
        merged = merge_similar_memories("p1", memory_type="project_fact")
        maintenance = run_memory_maintenance("p1")

        self.assertGreaterEqual(reinforced["importance_score"], item["importance_score"])
        self.assertIn("merged", merged)
        self.assertIn("archive", maintenance)


if __name__ == "__main__":
    unittest.main()
