import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.memory.memory_item import create_memory_item
from backend.researchos.memory.retrieval.hybrid_ranker import compute_memory_score, rank_memory_candidates
from backend.researchos.memory.retrieval.memory_retriever import retrieve_memories
from backend.researchos.memory.semantic.semantic_memory_store import create_semantic_memory_item, load_semantic_memory


class MemoryRetrieverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_retriever_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        self.item = create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="Cytokine claim", content="TLR4 increases cytokine release", source_ids=["src1"], importance_score=0.8))

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_retrieve_ranks_and_updates_access_stats(self) -> None:
        results = retrieve_memories("p1", "TLR4 cytokine", top_k=5)
        loaded = load_semantic_memory(self.item["memory_id"])

        self.assertTrue(results)
        self.assertIn("match_reason", results[0])
        self.assertEqual(loaded["retrieval_count"], 1)
        self.assertGreater(compute_memory_score(self.item, "TLR4 cytokine"), 0)
        self.assertEqual(rank_memory_candidates([self.item], "TLR4")[0]["memory_id"], self.item["memory_id"])


if __name__ == "__main__":
    unittest.main()
