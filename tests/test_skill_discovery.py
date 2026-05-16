import unittest
from pathlib import Path

from backend.researchos.agents.brain_agent import ResearchBrainAgent
from backend.researchos.skills.skill_catalog_loader import (
    get_skill_by_id,
    list_active_skills,
    list_pending_skills,
    resolve_skill_path,
    validate_skill_status,
)
from backend.researchos.skills.skill_discovery import (
    find_candidate_skills_for_query,
    get_skill_summary,
    rank_skill_candidates,
    search_skills,
)


ROOT = Path(__file__).resolve().parents[1]


class SkillDiscoveryTests(unittest.TestCase):
    def test_search_skills_finds_csv_parser(self) -> None:
        results = search_skills("分析 CSV")

        self.assertIn("parse-scientific-data", [item["skill_id"] for item in results])

    def test_search_skills_finds_sop_skills(self) -> None:
        results = search_skills("生成 SOP")

        self.assertTrue({"sop-generation", "protocol-extraction"} & {item["skill_id"] for item in results})

    def test_skill_catalog_loader_status_and_legacy_path(self) -> None:
        active = {item["skill_id"] for item in list_active_skills()}
        pending = {item["skill_id"] for item in list_pending_skills()}

        self.assertIn("parse-scientific-data", active)
        self.assertIn("generated-skill-template", pending)
        self.assertEqual(get_skill_by_id("parse-scientific-data")["status"], "active")
        self.assertTrue(resolve_skill_path("parse-scientific-data/SKILL.md").endswith("04_data_analysis_writing_review/parse-scientific-data/SKILL.md"))
        self.assertTrue(validate_skill_status("parse-scientific-data")["valid"])
        self.assertFalse(validate_skill_status("generated-skill-template")["valid"])

    def test_rank_skill_candidates_uses_intent_and_query(self) -> None:
        candidates = find_candidate_skills_for_query("分析 CSV")
        ranked = rank_skill_candidates(candidates, "分析 CSV", intent="data_analysis_to_narrative")

        self.assertEqual(ranked[0]["skill_id"], "parse-scientific-data")
        self.assertGreater(ranked[0]["score"], 0)

    def test_get_skill_summary_does_not_return_full_skill_doc(self) -> None:
        summary = get_skill_summary("parse-scientific-data")

        self.assertEqual(summary["skill_id"], "parse-scientific-data")
        self.assertNotIn("raw_markdown", summary)
        self.assertLess(len(str(summary)), 4000)

    def test_brain_plan_task_uses_discovery_without_full_skill_docs_when_pipeline_misses(self) -> None:
        brain = ResearchBrainAgent()
        spec = brain.plan_task("scientific data table cleanup", {"project_id": "p1", "intent": "unknown", "project_summary": "short"})

        self.assertEqual(spec.required_skills, ["parse-scientific-data"])
        self.assertNotIn("full_skill_catalog", spec.context_package)
        self.assertNotIn("full_skill_docs", spec.context_package)
        self.assertNotIn("SKILL.md", str(spec.context_package))


if __name__ == "__main__":
    unittest.main()
