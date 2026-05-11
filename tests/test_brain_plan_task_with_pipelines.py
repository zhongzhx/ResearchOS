import unittest

from backend.researchos.agents.brain_agent import ResearchBrainAgent


class BrainPlanTaskWithPipelinesTests(unittest.TestCase):
    def test_brain_plan_task_uses_pipeline_registry_for_literature_harvest(self) -> None:
        brain = ResearchBrainAgent()
        compiled = {"project_id": "p1", "intent": "literature_harvest", "project_summary": "short"}

        spec = brain.plan_task("帮我下载 LPS RAW264.7 文献", compiled)

        self.assertEqual(spec.task_type, "literature_harvest")
        self.assertEqual(spec.required_skills[:3], ["compliant-literature-access", "extract-first-article-keywords", "build-user-research-kb"])
        self.assertIn("delete_files", spec.forbidden_tools)
        self.assertEqual(spec.context_scope, "execution_minimal")
        self.assertNotIn("full_agent_memory", spec.context_package)

    def test_brain_plan_task_marks_browser_pipeline_as_waiting_for_authorization(self) -> None:
        brain = ResearchBrainAgent()
        compiled = {"project_id": "p1", "intent": "browser_research_learning", "project_summary": "short"}

        spec = brain.plan_task("用浏览器学习这个网页", compiled)

        self.assertEqual(spec.task_type, "browser_research_learning")
        self.assertIn("requires_user_authorization", spec.safety_constraints)
        self.assertFalse(spec.input_data.get("authorized", False))


if __name__ == "__main__":
    unittest.main()
