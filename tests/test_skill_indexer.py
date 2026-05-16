import json
import tempfile
import unittest
from pathlib import Path

from backend.researchos.skills.skill_indexer import (
    build_skill_index,
    extract_skill_summary_from_md,
    scan_skill_library,
    write_skill_catalog,
)


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "skills" / "researchos_skill_library"


class SkillIndexerTests(unittest.TestCase):
    def test_scan_skill_library_finds_canonical_skill_docs(self) -> None:
        docs = scan_skill_library(LIBRARY)

        self.assertIn(LIBRARY / "04_data_analysis_writing_review" / "parse-scientific-data" / "SKILL.md", docs)
        self.assertTrue(all(path.name == "SKILL.md" for path in docs))

    def test_extract_skill_summary_from_md_returns_safe_sections_not_full_doc(self) -> None:
        summary = extract_skill_summary_from_md(LIBRARY / "04_data_analysis_writing_review" / "parse-scientific-data" / "SKILL.md")

        self.assertEqual(summary["skill_id"], "parse-scientific-data")
        self.assertIn("Parse CSV", summary["description"])
        self.assertIn("csv_text", summary["inputs"])
        self.assertIn("row_count", summary["outputs"])
        self.assertIn("parse_scientific_data.py", summary["script_paths"])
        self.assertNotIn("raw_markdown", summary)

    def test_build_and_write_skill_index(self) -> None:
        index = build_skill_index(LIBRARY)
        rows = {row["skill_id"]: row for row in index["skills"]}

        self.assertIn("parse-scientific-data", rows)
        self.assertIn("sop-generation", rows)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "skill_catalog.generated.json"
            write_skill_catalog(index, output)
            written = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(written["version"], index["version"])
        self.assertGreater(len(written["skills"]), 0)


if __name__ == "__main__":
    unittest.main()
