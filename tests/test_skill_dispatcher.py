import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402
from backend.researchos.agents.agent_protocol import TaskSpec  # noqa: E402
from backend.researchos.execution.skill_dispatcher import get_active_skill, validate_required_skills  # noqa: E402


class SkillDispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aura_skill_dispatcher_"))
        self.agent_root = self.temp_dir / "agent_data"
        self.project = ros.create_project(self.agent_root, {"title": "Skill Test", "research_area": "test"})
        ros.upsert_skill(self.agent_root, {"skill_id": "active_skill", "skill_name": "ActiveSkill", "handler": "promoted_execution_memory", "status": "active"})
        ros.upsert_skill(self.agent_root, {"skill_id": "pending_skill", "skill_name": "PendingSkill", "handler": "promoted_execution_memory", "status": "pending_review"})

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_active_skill_can_be_loaded(self) -> None:
        skill = get_active_skill("ActiveSkill", agent_root=self.agent_root)

        self.assertEqual(skill["skill_id"], "active_skill")

    def test_pending_review_skill_is_rejected(self) -> None:
        result = validate_required_skills(["PendingSkill"], agent_root=self.agent_root)

        self.assertFalse(result["valid"])
        self.assertIn("PendingSkill", result["inactive_or_missing"])

    def test_active_skill_passes_validation(self) -> None:
        result = validate_required_skills(["ActiveSkill"], agent_root=self.agent_root)

        self.assertTrue(result["valid"])
        self.assertEqual(result["active"][0]["skill_name"], "ActiveSkill")


if __name__ == "__main__":
    unittest.main()
