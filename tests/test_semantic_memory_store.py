import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.brain.brain_page import create_brain_page
from backend.researchos.memory.memory_item import create_memory_item
from backend.researchos.memory.semantic.semantic_memory_store import (
    create_semantic_memory_item,
    find_semantic_duplicates,
    list_semantic_memories,
    sync_from_brain_pages,
    sync_to_brain_page,
)


class SemanticMemoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_semantic_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_and_sync_to_brain_page(self) -> None:
        item = create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="Claim A", content="Claim A text", source_ids=["src1"])
        created = create_semantic_memory_item(item)
        page = sync_to_brain_page(created)

        self.assertTrue(Path(page["path"]).exists())
        self.assertEqual(list_semantic_memories("p1", memory_type="claim")[0]["title"], "Claim A")

    def test_sync_from_brain_pages_and_find_duplicates(self) -> None:
        create_brain_page("claim", "claim-a", {"title": "Claim A", "project_id": "p1", "confidence": "medium", "source_ids": ["src1"]}, "Claim A text", [])
        synced = sync_from_brain_pages("p1")
        duplicates = find_semantic_duplicates("p1", create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="Claim A", content="Claim A text"))

        self.assertEqual(synced["created"], 1)
        self.assertTrue(duplicates)


if __name__ == "__main__":
    unittest.main()
