import unittest

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.execution.execution_result_validator import validate_execution_result
from backend.researchos.execution.tool_dispatcher import call_tool


class NotConnectedStatusTests(unittest.TestCase):
    def test_data_parser_not_connected_is_not_success(self) -> None:
        spec = TaskSpec(user_query="parse", task_type="data_analysis", allowed_tools=["data_parser"])
        result = call_tool("data_parser", {}, spec)

        execution = ExecutionResult(task_id=spec.task_id, status="success", structured_outputs={"tool": result})
        validation = validate_execution_result(execution, spec)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "not_connected")
        self.assertFalse(validation["valid"])


if __name__ == "__main__":
    unittest.main()
