import unittest
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "research-agent-runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402

from backend.researchos.agents.brain_agent import ResearchBrainAgent
from backend.researchos.agents.coordinator import AgentCoordinator
from backend.researchos.agents.execution_agent import ResearchExecutionAgent


class AgentCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aura_coordinator_"))
        self.agent_root = self.temp_dir / "agent_data"
        self.project = ros.create_project(self.agent_root, {"title": "Coordinator Test", "research_area": "test"})

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_brain_agent_generates_minimal_task_spec(self) -> None:
        brain = ResearchBrainAgent(agent_root=self.agent_root)

        compiled = brain.compile_context("总结当前知识库", self.project["id"], "kb_query")
        spec = brain.plan_task("总结当前知识库", compiled)

        self.assertEqual(spec.context_scope, "execution_minimal")
        self.assertTrue(spec.required_skills)
        self.assertTrue(spec.expected_outputs)
        self.assertTrue(spec.validation_rules)
        self.assertNotIn("compiled_context", spec.context_package)

    def test_execution_agent_fails_when_context_is_not_isolated(self) -> None:
        brain = ResearchBrainAgent(agent_root=self.agent_root)
        compiled = {"full_agent_memory": [{"secret": True}], "project_summary": "short"}
        spec = brain.plan_task("总结", compiled)
        spec.context_package["full_agent_memory"] = [{"secret": True}]
        execution = ResearchExecutionAgent(agent_root=self.agent_root)

        result = execution.execute_task(spec)

        self.assertEqual(result.status, "failed")
        self.assertTrue(result.errors)

    def test_agent_coordinator_runs_mock_dual_agent_flow(self) -> None:
        execution = ResearchExecutionAgent(agent_root=self.agent_root)
        coordinator = AgentCoordinator(brain_agent=ResearchBrainAgent(execution_agent=execution, agent_root=self.agent_root), execution_agent=execution)

        response = coordinator.run("总结当前知识库", project_id=self.project["id"])

        self.assertTrue(response["ok"])
        self.assertEqual(response["task_spec"]["context_scope"], "execution_minimal")
        self.assertEqual(response["execution_result"]["status"], "success")
        self.assertIn(response["brain_decision"]["decision_type"], {"accept", "revise", "retry", "ask_user", "write_memory", "crystallize_skill", "stop"})


if __name__ == "__main__":
    unittest.main()
