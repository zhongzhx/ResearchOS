import os
import shutil
import unittest
import uuid
from pathlib import Path

from backend.researchos.brain.skill_crystallizer import crystallize_skill_from_reflection
from backend.researchos.brain.skill_registry_review import activate_skill, register_pending_skill
from backend.researchos.skills.resolver_checker import check_duplicate_triggers, check_unreachable_skills, load_skill_resolver, route_intent_to_skill, run_resolver_smoke_tests


class ResolverCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        tmp_root = root / ".tmp" / "tests"
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.tmp = tmp_root / f"aura_resolver_{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        os.environ["RESEARCHOS_SKILLS_ROOT"] = str(self.tmp / "skills")

    def tearDown(self) -> None:
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        os.environ.pop("RESEARCHOS_SKILLS_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_core_resolver_and_health_report(self) -> None:
        resolver = load_skill_resolver()
        health = run_resolver_smoke_tests()

        self.assertIn("literature_harvest", resolver)
        self.assertIn("keyword-research-harvest", str(resolver))
        self.assertIn("warnings", health)
        self.assertIsInstance(check_unreachable_skills(), list)
        self.assertIsInstance(check_duplicate_triggers(), list)

    def test_pending_generated_skill_not_routed_until_active(self) -> None:
        skill = crystallize_skill_from_reflection({"skillrun_id": "sr1", "candidate_skill_name": "Custom Literature Scout", "candidate_skill_type": "literature_harvest", "reuse_score": 0.9, "risk_level": "low", "task_summary": "Custom scout."})
        register_pending_skill(skill["skill_dir"])

        pending = route_intent_to_skill("Custom Literature Scout")
        activate_skill("Custom Literature Scout")
        active = route_intent_to_skill("Custom Literature Scout")

        self.assertNotEqual(pending.get("skill_name"), "Custom Literature Scout")
        self.assertEqual(active.get("skill_name"), "Custom Literature Scout")


if __name__ == "__main__":
    unittest.main()
