import json
import unittest
from pathlib import Path

from backend.researchos.skills.pipeline_registry import load_skill_catalog, resolve_skill_path, route_query_to_pipeline


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "skills" / "researchos_skill_library"


class SkillCatalogTests(unittest.TestCase):
    def test_skill_catalog_lists_active_core_skills_with_existing_canonical_paths(self) -> None:
        catalog = load_skill_catalog()
        required = {
            "keyword-research-harvest",
            "compliant-literature-access",
            "extract-first-article-keywords",
            "build-user-research-kb",
            "plan-research-route",
            "parse-scientific-data",
            "weekly-research-report",
        }

        self.assertTrue(required.issubset(set(catalog)))
        for skill_id in required:
            row = catalog[skill_id]
            self.assertEqual(row["status"], "active")
            self.assertTrue((ROOT / row["canonical_path"]).exists(), row["canonical_path"])

    def test_legacy_path_map_resolves_old_skill_paths(self) -> None:
        resolved = resolve_skill_path("parse-scientific-data/SKILL.md")

        self.assertEqual(
            resolved.replace("\\", "/"),
            "skills/researchos_skill_library/04_data_analysis_writing_review/parse-scientific-data/SKILL.md",
        )
        self.assertTrue((ROOT / resolved).exists())

    def test_catalog_file_is_json_and_generated_skills_default_pending_review(self) -> None:
        data = json.loads((LIBRARY / "skill_catalog.json").read_text(encoding="utf-8"))

        self.assertIsInstance(data["skills"], list)
        generated = [item for item in data["skills"] if item.get("category") == "generated"]
        self.assertTrue(all(item["status"] == "pending_review" for item in generated))

    def test_chinese_literature_request_routes_to_literature_harvest(self) -> None:
        routed = route_query_to_pipeline("\u5e2e\u6211\u4e0b\u8f7d\u514d\u75ab\u8c03\u63a7\u76f8\u5173\u6587\u732e")

        self.assertEqual(routed["pipeline_name"], "literature_harvest")


if __name__ == "__main__":
    unittest.main()
