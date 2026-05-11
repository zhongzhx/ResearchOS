import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.brain.brain_page import create_brain_page, update_compiled_truth
from backend.researchos.brain.research_graph import graph_neighbors, rebuild_graph, remove_stale_edges_for_page, upsert_research_edge


class ResearchGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_graph_"))
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")

    def tearDown(self) -> None:
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_graph_edge_can_be_extracted_from_page(self) -> None:
        create_brain_page("claim", "claim-graph", {"title": "Claim", "project_id": "p1", "source_ids": ["paper-1"]}, "This claim supports claim-b and cites paper-1.", [])
        result = rebuild_graph("p1")

        self.assertGreaterEqual(result["edge_count"], 1)
        self.assertTrue(graph_neighbors("claim-graph"))

    def test_stale_edges_removed_after_update(self) -> None:
        upsert_research_edge({"source_slug": "a", "target_slug": "b", "relation_type": "supports", "confidence": "medium", "extraction_method": "test"})
        self.assertTrue(graph_neighbors("a"))

        removed = remove_stale_edges_for_page("a")

        self.assertGreaterEqual(removed["removed"], 1)
        self.assertEqual(graph_neighbors("a"), [])


if __name__ == "__main__":
    unittest.main()
