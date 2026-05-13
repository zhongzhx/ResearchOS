import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "research-agent-runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from backend.researchos.agents.agent_protocol import TaskSpec  # noqa: E402
from backend.researchos.execution.tool_dispatcher import call_tool, validate_allowed_tool  # noqa: E402


class ToolDispatcherTests(unittest.TestCase):
    def test_forbidden_tool_is_rejected(self) -> None:
        spec = TaskSpec(user_query="run", intent="start_skill_request", task_type="generic_skill_task", allowed_tools=["file_reader"], forbidden_tools=["file_reader"])

        result = validate_allowed_tool("file_reader", spec)

        self.assertFalse(result["valid"])
        self.assertIn("forbidden", result["errors"][0])

    def test_undeclared_input_file_cannot_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "secret.txt"
            path.write_text("secret", encoding="utf-8")
            spec = TaskSpec(user_query="read", intent="start_skill_request", task_type="generic_skill_task", allowed_tools=["file_reader"], input_files=[])

            result = call_tool("file_reader", {"path": str(path)}, spec)

            self.assertFalse(result["ok"])
            self.assertIn("not declared", result["error"])

    def test_script_runner_records_stdout_stderr_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "hello.py"
            script.write_text("print('hello')", encoding="utf-8")
            spec = TaskSpec(user_query="script", intent="start_skill_request", task_type="generic_skill_task", allowed_tools=["script_runner"], input_data={"workspace_base_dir": tmp})

            result = call_tool("script_runner", {"command": [sys.executable, str(script)]}, spec)

        self.assertTrue(result["ok"])
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("hello", result["stdout"])
        self.assertIn("stderr", result)


if __name__ == "__main__":
    unittest.main()
