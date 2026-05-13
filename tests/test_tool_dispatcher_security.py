import tempfile
import unittest
from pathlib import Path

from backend.researchos.agents.agent_protocol import TaskSpec
from backend.researchos.execution.tool_dispatcher import call_tool, validate_allowed_tool


class ToolDispatcherSecurityTests(unittest.TestCase):
    def test_forbidden_tool_is_rejected(self) -> None:
        spec = TaskSpec(user_query="run", allowed_tools=["file_reader"], forbidden_tools=["file_reader"])

        result = validate_allowed_tool("file_reader", spec)

        self.assertFalse(result["valid"])
        self.assertTrue(any("forbidden" in issue for issue in result["errors"]))

    def test_undeclared_input_file_cannot_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.txt"
            path.write_text("content", encoding="utf-8")
            spec = TaskSpec(user_query="read", allowed_tools=["file_reader"], input_files=[], input_data={"workspace_base_dir": str(Path(tmp) / "workspace")})

            result = call_tool("file_reader", {"path": str(path)}, spec)

        self.assertFalse(result["ok"])
        self.assertIn("not declared", result["error"])

    def test_env_file_cannot_be_read_even_when_declared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("OPENAI_API_KEY=sk-test12345", encoding="utf-8")
            spec = TaskSpec(user_query="read", allowed_tools=["file_reader"], input_files=[str(path)], input_data={"workspace_base_dir": str(Path(tmp) / "workspace")})

            result = call_tool("file_reader", {"path": str(path)}, spec)

        self.assertFalse(result["ok"])
        self.assertIn("sensitive", result["error"])

    def test_data_secrets_cannot_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data" / "secrets" / "token.txt"
            path.parent.mkdir(parents=True)
            path.write_text("token=abc", encoding="utf-8")
            spec = TaskSpec(user_query="read", allowed_tools=["file_reader"], input_files=[str(path)], input_data={"workspace_base_dir": str(Path(tmp) / "workspace")})

            result = call_tool("file_reader", {"path": str(path)}, spec)

        self.assertFalse(result["ok"])
        self.assertIn("sensitive", result["error"])


if __name__ == "__main__":
    unittest.main()
