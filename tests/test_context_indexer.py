import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.brain.brain_page import create_brain_page
from backend.researchos.brain.context_indexer import build_project_context_index, load_project_context_index, select_high_value_context


class ContextIndexerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_context_index_"))
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")

    def tearDown(self) -> None:
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_index_counts_assets_without_full_chunks_or_logs(self) -> None:
        create_brain_page("claim", "claim-index", {"title": "Claim", "project_id": "p1", "confidence": "high", "source_ids": ["s1"]}, "Compiled truth only.", [])
        create_brain_page("failure", "failure-index", {"title": "Failure", "project_id": "p1"}, "A failed run.", [])

        index = build_project_context_index("p1")
        loaded = load_project_context_index("p1")

        self.assertEqual(index["available_assets"]["claims"], 1)
        self.assertEqual(index["available_assets"]["failures"], 1)
        self.assertNotIn("full_chunk", str(index).lower())
        self.assertEqual(loaded["project_id"], "p1")

    def test_select_high_value_context_returns_intent_specific_items(self) -> None:
        create_brain_page("claim", "claim-mechanism", {"title": "Mechanism", "project_id": "p1", "confidence": "high", "source_ids": ["s1"]}, "Compiled truth.", [])
        build_project_context_index("p1")

        context = select_high_value_context("p1", "mechanism_reasoning", "mechanism")

        self.assertTrue(context["selected"])


if __name__ == "__main__":
    unittest.main()
