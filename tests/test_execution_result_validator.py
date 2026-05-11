import unittest

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.execution.execution_result_validator import validate_execution_result


class ExecutionResultValidatorTests(unittest.TestCase):
    def test_missing_expected_outputs_are_reported(self) -> None:
        spec = TaskSpec(user_query="report", intent="start_skill_request", task_type="report_generation", expected_outputs=["output_files"], context_package={"task_brief": "report"})
        result = ExecutionResult(task_id=spec.task_id, status="success", summary="no files")

        report = validate_execution_result(result, spec)

        self.assertFalse(report["valid"])
        self.assertTrue(report["issues"])

    def test_forbidden_tool_usage_is_reported(self) -> None:
        spec = TaskSpec(user_query="run", intent="start_skill_request", task_type="generic_skill_task", forbidden_tools=["file_reader"], context_package={"task_brief": "run"})
        result = ExecutionResult(task_id=spec.task_id, status="success", logs=["tool:file_reader"])

        report = validate_execution_result(result, spec)

        self.assertFalse(report["valid"])
        self.assertTrue(any("forbidden tool" in issue for issue in report["issues"]))


if __name__ == "__main__":
    unittest.main()
