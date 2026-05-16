import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402
from backend.researchos.agents.brain_agent import ResearchBrainAgent  # noqa: E402
from backend.researchos.agents.coordinator import AgentCoordinator  # noqa: E402
from backend.researchos.brain.skill_registry_review import list_pending_skills  # noqa: E402


class BrainAgentEvolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_evolution_"))
        self.agent_root = self.tmp / "agent_data"
        self.brain_root = self.tmp / "research_brain"
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.agent_root)
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.brain_root)
        os.environ["RESEARCHOS_SKILLS_ROOT"] = str(self.tmp / "skills")
        self.project = ros.create_project(self.agent_root, {"title": "Evolution", "research_area": "test"})

    def tearDown(self) -> None:
        for key in ["RESEARCHOS_AGENT_ROOT", "RESEARCH_BRAIN_ROOT", "RESEARCHOS_SKILLS_ROOT"]:
            os.environ.pop(key, None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _completed_skillrun(self) -> str:
        run = ros.start_service_skill_run(self.agent_root, "core_report_writer", "Report Writer", self.project["id"], {"task_type": "report_generation", "user_query": "write report"})
        ros.update_skill_run(self.agent_root, run["id"], status="completed", output_payload={"structured_outputs": {"report": "ok"}, "output_files": ["report.md"]}, output_object_refs=[{"type": "report", "id": "r1"}], logs=["tool:file_writer", "completed"])
        return run["id"]

    def test_process_completed_skillrun_full_evolution_loop(self) -> None:
        skillrun_id = self._completed_skillrun()
        brain = ResearchBrainAgent(agent_root=self.agent_root)

        result = brain.process_completed_skillrun(skillrun_id)

        self.assertTrue(result["reflection"]["should_update_brain"])
        self.assertTrue(result["memory_write"]["pages"])
        self.assertTrue(result["context_index"]["project_id"])
        self.assertTrue(result["pending_skill"])
        self.assertEqual(result["pending_skill"]["status"], "pending_review")
        self.assertTrue(list_pending_skills())

    def test_coordinator_delegates_completed_skillrun_processing(self) -> None:
        skillrun_id = self._completed_skillrun()
        coordinator = AgentCoordinator(brain_agent=ResearchBrainAgent(agent_root=self.agent_root))

        result = coordinator.process_completed_skillrun(skillrun_id)

        self.assertTrue(result["ok"])
        self.assertEqual(result["skillrun_id"], skillrun_id)


if __name__ == "__main__":
    unittest.main()
