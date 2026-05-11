import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.brain.skill_crystallizer import crystallize_skill_from_reflection, validate_candidate_before_register


class SkillCrystallizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_crystallizer_"))
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        os.environ["RESEARCHOS_SKILLS_ROOT"] = str(self.tmp / "skills")

    def tearDown(self) -> None:
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        os.environ.pop("RESEARCHOS_SKILLS_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_high_reuse_reflection_generates_pending_skill(self) -> None:
        result = crystallize_skill_from_reflection({"skillrun_id": "sr1", "candidate_skill_name": "Report Draft Builder", "candidate_skill_type": "report_generation", "reuse_score": 0.91, "risk_level": "medium", "requires_user_review": True, "task_summary": "Builds a report draft."})

        skill_dir = Path(result["skill_dir"])
        manifest = json.loads((skill_dir / "skill.json").read_text(encoding="utf-8"))
        markdown = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

        self.assertEqual(manifest["status"], "pending_review")
        self.assertEqual(manifest["created_from_skillrun_id"], "sr1")
        for heading in ["# Purpose", "# When to Use", "# Inputs", "# Outputs", "# Procedure", "# Validation", "# Failure Modes", "# Human Review Requirements", "# Provenance"]:
            self.assertIn(heading, markdown)
        self.assertTrue(validate_candidate_before_register(str(skill_dir))["valid"])


if __name__ == "__main__":
    unittest.main()
