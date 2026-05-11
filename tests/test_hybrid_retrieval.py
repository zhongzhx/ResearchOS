import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.brain.brain_page import create_brain_page
from backend.researchos.brain.hybrid_retrieval import hybrid_search, rrf_fuse, source_aware_dedup


class HybridRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_hybrid_"))
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")

    def tearDown(self) -> None:
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rrf_and_dedup(self) -> None:
        fused = rrf_fuse([[{"source_id": "a", "score": 1}], [{"source_id": "a", "score": 2}, {"source_id": "b", "score": 1}]])
        deduped = source_aware_dedup(fused)

        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["source_id"], "a")

    def test_hybrid_search_uses_keyword_and_keeps_source_metadata(self) -> None:
        create_brain_page("paper", "paper-raw", {"title": "RAW264.7 paper", "project_id": "p1", "confidence": "medium", "source_ids": ["doi:1"]}, "RAW264.7 macrophage inflammation evidence.", [])

        results = hybrid_search("RAW264.7 inflammation", project_id="p1")

        self.assertTrue(results)
        self.assertIn("page_slug", results[0])
        self.assertIn("confidence", results[0])


if __name__ == "__main__":
    unittest.main()
