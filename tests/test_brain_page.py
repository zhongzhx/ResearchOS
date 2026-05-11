import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.brain.brain_page import (
    append_timeline_event,
    create_brain_page,
    parse_brain_page,
    read_brain_page,
    render_brain_page,
    update_compiled_truth,
)


class BrainPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_brain_page_"))
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")

    def tearDown(self) -> None:
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_compiled_truth_update_keeps_timeline(self) -> None:
        page = create_brain_page(
            "claim",
            "claim-a",
            {"title": "Claim A", "project_id": "p1", "source_ids": ["src1"], "confidence": "medium"},
            "Initial truth.",
            [{"evidence_type": "paper", "confidence": "medium", "source_ids": ["src1"], "event": "First evidence", "impact": "Created"}],
        )

        updated = update_compiled_truth("claim-a", "Updated truth with src1.", "new evidence", ["src1"], "high")

        self.assertIn("Initial truth", page["compiled_truth"])
        self.assertEqual(updated["compiled_truth"], "Updated truth with src1.")
        self.assertGreaterEqual(len(updated["timeline_entries"]), 2)
        self.assertTrue(any("First evidence" in item.get("event", "") for item in updated["timeline_entries"]))

    def test_timeline_append_only(self) -> None:
        create_brain_page("paper", "paper-a", {"title": "Paper A", "project_id": "p1"}, "Paper summary.", [])

        first = append_timeline_event("paper-a", {"evidence_type": "paper", "confidence": "low", "source_ids": ["s1"], "event": "A", "impact": "B"})
        second = append_timeline_event("paper-a", {"evidence_type": "paper", "confidence": "medium", "source_ids": ["s2"], "event": "C", "impact": "D"})

        self.assertEqual(len(first["timeline_entries"]), 1)
        self.assertEqual(len(second["timeline_entries"]), 2)
        self.assertEqual(second["timeline_entries"][0]["event"], "A")

    def test_render_and_parse_roundtrip(self) -> None:
        page = create_brain_page("dataset", "dataset-a", {"title": "Dataset A", "project_id": "p1", "tags": ["qPCR"]}, "Rows parsed.", [])
        parsed = parse_brain_page(render_brain_page(page))
        read = read_brain_page("dataset-a")

        self.assertEqual(parsed["frontmatter"]["slug"], "dataset-a")
        self.assertEqual(read["compiled_truth"], "Rows parsed.")


if __name__ == "__main__":
    unittest.main()
