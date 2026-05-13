import unittest
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        self.assertIn("validation_report", response)
        self.assertIn("promotion_decision", response)
        self.assertIn("memory_commit", response)
        self.assertIn("rejected_items", response)
        self.assertIn("required_human_review", response)

    def test_coordinator_main_chain_does_not_direct_write_memory_from_result(self) -> None:
        execution = ResearchExecutionAgent(agent_root=self.agent_root)
        brain = ResearchBrainAgent(execution_agent=execution, agent_root=self.agent_root)
        brain.write_memory_from_result = MagicMock(side_effect=AssertionError("direct memory write is forbidden in coordinator main chain"))
        coordinator = AgentCoordinator(brain_agent=brain, execution_agent=execution)

        response = coordinator.run("总结当前知识库", project_id=self.project["id"])

        self.assertTrue(response["ok"])
        brain.write_memory_from_result.assert_not_called()
        self.assertEqual(response["memory_commit"]["control_skill"], "memory_commit")

    def test_graph_and_context_index_update_after_memory_commit(self) -> None:
        execution = ResearchExecutionAgent(agent_root=self.agent_root)
        brain = ResearchBrainAgent(execution_agent=execution, agent_root=self.agent_root)
        sequence: list[str] = []
        original_commit = brain.commit_promoted_memory

        def commit_then_record(promotion_decision):
            sequence.append("memory_commit")
            return original_commit(promotion_decision)

        def graph_update(project_id):
            sequence.append("graph_update")
            return {"edge_count": 0, "rebuilt_count": 0}

        def index_update(project_id):
            sequence.append("context_index")
            return {"project_id": project_id}

        brain.commit_promoted_memory = commit_then_record
        brain.update_research_graph = graph_update
        brain.update_context_index = index_update
        coordinator = AgentCoordinator(brain_agent=brain, execution_agent=execution)

        coordinator.run("总结当前知识库", project_id=self.project["id"])

        self.assertIn("memory_commit", sequence)
        self.assertEqual(sequence.index("memory_commit") < sequence.index("graph_update") < sequence.index("context_index"), True)

    def test_coordinator_response_exposes_rejection_for_secret_leak(self) -> None:
        execution = ResearchExecutionAgent(agent_root=self.agent_root)
        brain = ResearchBrainAgent(execution_agent=execution, agent_root=self.agent_root)
        coordinator = AgentCoordinator(brain_agent=brain, execution_agent=execution)

        with patch.object(execution, "execute_task") as execute_task:
            from backend.researchos.agents.agent_protocol import ExecutionResult

            execute_task.return_value = ExecutionResult(task_id="t1", status="success", summary="api key sk-test leaked")
            response = coordinator.run("download literature", project_id=self.project["id"])

        self.assertTrue(response["rejected_items"])
        self.assertTrue(response["required_human_review"])
        self.assertEqual(response["memory_commit"]["pages"], [])


if __name__ == "__main__":
    unittest.main()
