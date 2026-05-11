import unittest

from backend.researchos.agents.brain_agent import ResearchBrainAgent


class ContextCompilerMaintenanceSkillTests(unittest.TestCase):
    def test_plan_task_marks_context_package_as_sanitized_by_maintenance_skill(self) -> None:
        brain = ResearchBrainAgent()
        compiled = {"project_id": "p1", "intent": "data_analysis_to_narrative", "full_agent_memory": ["blocked"], "project_summary": "short"}

        spec = brain.plan_task("分析 CSV 并写结果段", compiled)

        self.assertEqual(spec.context_scope, "execution_minimal")
        self.assertEqual(spec.context_redaction_report["control_skill"], "context-compiler-maintenance")
        self.assertNotIn("full_agent_memory", spec.context_package)


if __name__ == "__main__":
    unittest.main()
