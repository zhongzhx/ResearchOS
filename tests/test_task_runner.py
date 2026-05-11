import unittest
import tempfile

from backend.researchos.agents.agent_protocol import TaskSpec
from backend.researchos.execution.task_runner import build_execution_plan, run_execution_plan


class TaskRunnerTests(unittest.TestCase):
    def test_unknown_task_type_returns_failed_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = TaskSpec(user_query="unknown", intent="start_skill_request", task_type="unknown_task", input_data={"workspace_base_dir": tmp}, context_package={"task_brief": "unknown"})

            plan = build_execution_plan(spec)
            result = run_execution_plan(plan, spec)

        self.assertEqual(plan["status"], "failed")
        self.assertFalse(result["ok"])

    def test_supported_task_type_builds_plan(self) -> None:
        spec = TaskSpec(user_query="qa", intent="kb_query", task_type="rag_question_answering", allowed_tools=["rag_query"], context_package={"task_brief": "qa"})

        plan = build_execution_plan(spec)

        self.assertEqual(plan["status"], "ready")
        self.assertIn("rag_query", plan["tools"])


if __name__ == "__main__":
    unittest.main()
