import unittest

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.execution.execution_result_validator import validate_execution_result


class ExecutionResultValidatorSecurityTests(unittest.TestCase):
    def test_parser_not_connected_is_reported(self) -> None:
        spec = TaskSpec(user_query="parse pdf", allowed_tools=["pdf_parser"], expected_outputs=["structured_outputs"])
        result = ExecutionResult(
            task_id=spec.task_id,
            status="failed",
            structured_outputs={"tool_results": [{"tool_name": "pdf_parser", "status": "not_connected"}]},
            validation_report={"checked": True},
        )

        report = validate_execution_result(result, spec)

        self.assertFalse(report["valid"])
        self.assertTrue(any("not_connected" in issue for issue in report["issues"]))

    def test_secret_leakage_is_reported(self) -> None:
        spec = TaskSpec(user_query="run")
        result = ExecutionResult(task_id=spec.task_id, status="success", summary="api key sk-test12345", validation_report={"checked": True})

        report = validate_execution_result(result, spec)

        self.assertFalse(report["valid"])
        self.assertTrue(any("secret leakage" in issue for issue in report["issues"]))

    def test_missing_validation_report_can_be_required(self) -> None:
        spec = TaskSpec(user_query="run")
        result = ExecutionResult(task_id=spec.task_id, status="success")

        report = validate_execution_result(result, spec, require_validation_report=True)

        self.assertFalse(report["valid"])
        self.assertTrue(any("missing validation report" in issue for issue in report["issues"]))


if __name__ == "__main__":
    unittest.main()
