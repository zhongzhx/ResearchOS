import json
import unittest
from pathlib import Path

from backend.researchos.skills.pipeline_registry import load_skill_catalog


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "skills" / "researchos_skill_library" / "01_core_runtime_memory"


class GlueSkillsCatalogTests(unittest.TestCase):
    def test_glue_skill_folders_have_skill_md_and_manifest(self) -> None:
        for name in ["skill-router-orchestrator", "evidence-promotion", "context-compiler-maintenance", "skill-output-validator"]:
            self.assertTrue((CORE / name / "SKILL.md").exists(), name)
            self.assertTrue((CORE / name / "skill.json").exists(), name)

    def test_catalog_contains_active_brain_control_glue_skills(self) -> None:
        catalog = load_skill_catalog()
        for name in ["skill-router-orchestrator", "evidence-promotion", "context-compiler-maintenance", "skill-output-validator"]:
            row = catalog[name]
            self.assertEqual(row["category"], "01_core_runtime_memory")
            self.assertEqual(row["status"], "active")
            self.assertEqual(row["owner"]["planner"], "brain_agent")
            self.assertIsNone(row["owner"]["executor"])
            self.assertTrue((ROOT / row["canonical_path"]).exists())

    def test_skill_json_matches_catalog_status(self) -> None:
        catalog = load_skill_catalog()
        for name in ["skill-router-orchestrator", "evidence-promotion", "context-compiler-maintenance", "skill-output-validator"]:
            manifest = json.loads((CORE / name / "skill.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["name"], name)
            self.assertEqual(manifest["status"], catalog[name]["status"])
            self.assertEqual(manifest["planner_agent"], "brain_agent")
            self.assertIsNone(manifest["executor_agent"])


if __name__ == "__main__":
    unittest.main()
