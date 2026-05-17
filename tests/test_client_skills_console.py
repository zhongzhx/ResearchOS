import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS_JS = ROOT / "web_client" / "views" / "skills.js"
CATALOG = ROOT / "skills" / "researchos_skill_library" / "skill_catalog.json"


class ClientSkillsConsoleTests(unittest.TestCase):
    def test_skills_console_filters_by_category_risk_authorization_auto_call_and_status(self) -> None:
        source = SKILLS_JS.read_text(encoding="utf-8")

        for marker in ["categoryFilter", "riskFilter", "authorizationFilter", "autoCallFilter", "statusFilter"]:
            self.assertIn(marker, source)

        for field in [
            "skill_id",
            "display_name",
            "category",
            "canonical_path",
            "risk_level",
            "allowed_auto_call",
            "requires_user_authorization",
            "input_types",
            "output_types",
            "promotion_targets",
        ]:
            self.assertIn(field, source)

    def test_high_risk_and_internal_control_skills_are_not_rendered_as_runnable_scripts(self) -> None:
        source = SKILLS_JS.read_text(encoding="utf-8")

        self.assertIn("需要授权", source)
        self.assertIn("internal/control", source)
        for internal in ["skill-router-orchestrator", "evidence-promotion", "context-compiler-maintenance", "skill-output-validator"]:
            self.assertIn(internal, source)

        self.assertNotIn("runLegacySkill", source)
        self.assertNotIn("运行技能", source)

    def test_route_tester_is_human_readable_and_catalog_excludes_global_runtime(self) -> None:
        source = SKILLS_JS.read_text(encoding="utf-8")
        catalog = json.loads(CATALOG.read_text(encoding="utf-8-sig"))
        skill_ids = {str(item.get("skill_id") or "") for item in catalog.get("skills", [])}

        self.assertIn("selected pipeline", source)
        self.assertIn("required skills", source)
        self.assertIn("authorization needed", source)
        self.assertIn("risk flags", source)
        self.assertIn("reason", source)
        self.assertIn("raw JSON", source)
        self.assertNotIn("research-agent-runtime", skill_ids)


if __name__ == "__main__":
    unittest.main()
