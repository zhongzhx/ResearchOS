import unittest

from backend.researchos.agents.brain_agent import ResearchBrainAgent
from backend.researchos.agents.coordinator import AgentCoordinator
from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.execution.runtime_adapter import check_pipeline_authorization, check_skill_authorization
from backend.researchos.skills.pipeline_registry import get_pipeline_for_intent


class SpyExecutionAgent:
    def __init__(self) -> None:
        self.called = False

    def execute_task(self, task_spec: TaskSpec) -> ExecutionResult:
        self.called = True
        return ExecutionResult(task_id=task_spec.task_id, status="success", summary="called")


class AuthorizationGatingTests(unittest.TestCase):
    def test_browser_pipeline_without_authorization_does_not_dispatch(self) -> None:
        execution = SpyExecutionAgent()
        brain = ResearchBrainAgent(execution_agent=execution)
        coordinator = AgentCoordinator(brain_agent=brain, execution_agent=execution)

        response = coordinator.run("use browser to learn this page", project_id="p1")

        self.assertFalse(execution.called)
        self.assertFalse(response["ok"])
        self.assertEqual(response["brain_decision"]["decision_type"], "ask_user")
        self.assertTrue(response["required_human_review"])

    def test_authorized_browser_pipeline_marks_task_spec_authorized(self) -> None:
        brain = ResearchBrainAgent()
        spec = brain.plan_task(
            "use browser to learn this page",
            {"project_id": "p1", "intent": "browser_research_learning", "user_authorization_flags": {"browser": True}},
        )
        pipeline = get_pipeline_for_intent("browser_research_learning")

        authorization = check_pipeline_authorization(spec, pipeline)

        self.assertTrue(authorization["valid"])
        self.assertTrue(spec.input_data["authorized"])
        self.assertIn("requires_user_authorization", spec.safety_constraints)

    def test_browser_skill_requires_authorization(self) -> None:
        blocked = check_skill_authorization(["browser-use"], {})
        allowed = check_skill_authorization(["browser-use"], {"browser": True})

        self.assertFalse(blocked["valid"])
        self.assertTrue(allowed["valid"])


if __name__ == "__main__":
    unittest.main()
