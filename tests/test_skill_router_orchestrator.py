import unittest

from backend.researchos.agents.brain_agent import ResearchBrainAgent


class SkillRouterOrchestratorTests(unittest.TestCase):
    def test_plan_task_records_pre_dispatch_control_skills(self) -> None:
        brain = ResearchBrainAgent()

        spec = brain.plan_task("帮我下载 LPS 文献", {"project_id": "p1", "intent": "literature_harvest"})

        self.assertEqual(spec.input_data["control_skills"]["pre_dispatch"], ["skill-router-orchestrator", "context-compiler-maintenance"])
        self.assertEqual(spec.input_data["routing_control_skill"], "skill-router-orchestrator")
        self.assertEqual(spec.input_data["context_control_skill"], "context-compiler-maintenance")


if __name__ == "__main__":
    unittest.main()
