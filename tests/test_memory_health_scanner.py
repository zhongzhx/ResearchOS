import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.memory.learning.memory_health_scanner import (
    find_conflicting_claims,
    find_context_bloat,
    find_duplicate_memories,
    find_stale_memories,
    find_unsupported_claims,
    scan_memory_health,
)
from backend.researchos.memory.memory_item import create_memory_item
from backend.researchos.memory.semantic.semantic_memory_store import create_semantic_memory_item


class MemoryHealthScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_health_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="Unsupported", content="Unsupported claim", confidence="medium"))
        create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="Dup", content="Duplicate claim", source_ids=["s1"]))
        create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="Dup", content="Duplicate claim", source_ids=["s2"]))
        create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="A", content="TLR4 increases IL6", source_ids=["s3"]))
        create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="B", content="TLR4 decreases IL6", source_ids=["s4"]))

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_health_scanner_finds_quality_issues(self) -> None:
        report = scan_memory_health("p1")

        self.assertTrue(find_unsupported_claims("p1"))
        self.assertTrue(find_duplicate_memories("p1"))
        self.assertTrue(find_conflicting_claims("p1"))
        self.assertIn("stale_memories", report)
        self.assertIn("estimated_context_items", find_context_bloat("p1"))
        self.assertIsInstance(find_stale_memories("p1"), list)


if __name__ == "__main__":
    unittest.main()
