import unittest

from backend.researchos.agents.agent_protocol import TaskSpec
from backend.researchos.execution.tool_dispatcher import call_tool


class ParserAdapterStatusTests(unittest.TestCase):
    def test_pdf_parser_returns_not_connected(self) -> None:
        spec = TaskSpec(user_query="parse pdf", allowed_tools=["pdf_parser"])

        result = call_tool("pdf_parser", {}, spec)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "not_connected")
        self.assertIn("pdf_parser is not connected", result["message"])

    def test_data_parser_returns_not_connected(self) -> None:
        spec = TaskSpec(user_query="parse data", allowed_tools=["data_parser"])

        result = call_tool("data_parser", {}, spec)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "not_connected")
        self.assertIn("data_parser is not connected", result["message"])


if __name__ == "__main__":
    unittest.main()
