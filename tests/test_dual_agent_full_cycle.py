import os
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
from backend.researchos.agents.brain_agent import ResearchBrainAgent  # noqa: E402
from backend.researchos.agents.coordinator import AgentCoordinator  # noqa: E402
from backend.researchos.agents.execution_agent import ResearchExecutionAgent  # noqa: E402
from backend.researchos.brain.skill_registry_review import activate_skill, list_pending_skills, reject_skill  # noqa: E402
from backend.researchos.demo.dual_agent_demo import run_demo_pdf_evidence_flow  # noqa: E402


class DualAgentFullCycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_full_cycle_"))
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.tmp / "agent_data")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        os.environ["RESEARCHOS_SKILLS_ROOT"] = str(self.tmp / "skills")
        self.agent_root = Path(os.environ["RESEARCHOS_AGENT_ROOT"])
        self.project = ros.create_project(self.agent_root, {"title": "Full Cycle", "research_area": "demo"})

    def tearDown(self) -> None:
        for key in ["RESEARCHOS_AGENT_ROOT", "RESEARCH_BRAIN_ROOT", "RESEARCHOS_SKILLS_ROOT"]:
            os.environ.pop(key, None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_full_cycle_returns_execution_and_processing_summary(self) -> None:
        execution = ResearchExecutionAgent(agent_root=self.agent_root)
        coordinator = AgentCoordinator(ResearchBrainAgent(execution_agent=execution, agent_root=self.agent_root), execution)

        response = coordinator.run_full_cycle("write demo report", project_id=self.project["id"])

        self.assertTrue(response["ok"])
        self.assertIn("execution_result", response)
        self.assertIn("post_task_processing", response)
        self.assertTrue(response["post_task_processing"]["reflection"])
        self.assertTrue(response["post_task_processing"]["pending_skill"])

    def test_pending_skill_can_be_activated_or_rejected(self) -> None:
        response = run_demo_pdf_evidence_flow(self.project["id"])
        pending = list_pending_skills()

        self.assertTrue(pending)
        name = pending[0]["name"]
        active = activate_skill(name)
        self.assertEqual(active["status"], "active")

        response = run_demo_pdf_evidence_flow(self.project["id"])
        pending = list_pending_skills()
        name = pending[0]["name"]
        rejected = reject_skill(name, "not good enough")
        self.assertEqual(rejected["rejection_reason"], "not good enough")

    def test_demo_flow_summary_contains_expected_sections(self) -> None:
        summary = run_demo_pdf_evidence_flow(self.project["id"])

        self.assertTrue(summary["ok"])
        self.assertIn("task_spec", summary)
        self.assertIn("execution_result", summary)
        self.assertIn("brain_memory", summary)
        self.assertIn("pending_skill", summary)


if __name__ == "__main__":
    unittest.main()
