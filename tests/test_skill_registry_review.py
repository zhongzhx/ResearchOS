import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.brain.skill_crystallizer import crystallize_skill_from_reflection
from backend.researchos.brain.skill_registry_review import activate_skill, deprecate_skill, get_skill_status, list_pending_skills, register_pending_skill, reject_skill


class SkillRegistryReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_review_"))
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        os.environ["RESEARCHOS_SKILLS_ROOT"] = str(self.tmp / "skills")
        self.skill = crystallize_skill_from_reflection({"skillrun_id": "sr1", "candidate_skill_name": "Reusable Report", "candidate_skill_type": "report_generation", "reuse_score": 0.9, "risk_level": "low", "task_summary": "Reusable report."})

    def tearDown(self) -> None:
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        os.environ.pop("RESEARCHOS_SKILLS_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pending_activate_reject_deprecate(self) -> None:
        registered = register_pending_skill(self.skill["skill_dir"])
        self.assertEqual(registered["status"], "pending_review")
        self.assertTrue(list_pending_skills())

        active = activate_skill("Reusable Report")
        self.assertEqual(active["status"], "active")

        deprecated = deprecate_skill("Reusable Report", "replaced")
        self.assertEqual(deprecated["status"], "deprecated")

        rejected = reject_skill("Reusable Report", "bad output")
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(get_skill_status("Reusable Report")["rejection_reason"], "bad output")


if __name__ == "__main__":
    unittest.main()
