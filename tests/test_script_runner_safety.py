import sys
import tempfile
import unittest
from pathlib import Path

from backend.researchos.agents.agent_protocol import TaskSpec
from backend.researchos.execution.tool_dispatcher import call_tool


class ScriptRunnerSafetyTests(unittest.TestCase):
    def test_script_runner_rejects_dangerous_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = TaskSpec(user_query="script", allowed_tools=["script_runner"], input_data={"workspace_base_dir": tmp})

            result = call_tool("script_runner", {"command": ["rm", "-rf", "."]}, spec)

        self.assertFalse(result["ok"])
        self.assertIn("only allows Python", result["error"])

    def test_script_runner_rejects_inline_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = TaskSpec(user_query="script", allowed_tools=["script_runner"], input_data={"workspace_base_dir": tmp})

            result = call_tool("script_runner", {"command": [sys.executable, "-c", "print('x')"]}, spec)

        self.assertFalse(result["ok"])
        self.assertIn("inline Python", result["error"])

    def test_script_runner_redacts_secret_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "print_secret.py"
            script.write_text("print('api key sk-test12345 token=abc')", encoding="utf-8")
            spec = TaskSpec(user_query="script", allowed_tools=["script_runner"], input_data={"workspace_base_dir": tmp})

            result = call_tool("script_runner", {"command": [sys.executable, str(script)], "max_output_chars": 200}, spec)

        self.assertTrue(result["ok"])
        self.assertIn("[REDACTED]", result["stdout"])
        self.assertNotIn("sk-test12345", result["stdout"])
        self.assertNotIn("token=abc", result["stdout"])

    def test_script_runner_rejects_cwd_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp).parent
            spec = TaskSpec(user_query="script", allowed_tools=["script_runner"], input_data={"workspace_base_dir": tmp})

            result = call_tool("script_runner", {"command": [sys.executable, "-m", "py_compile"], "cwd": str(outside)}, spec)

        self.assertFalse(result["ok"])
        self.assertIn("cwd", result["error"])

    def test_script_runner_reports_missing_dependency_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "run.py"
            script.write_text("print('should not execute')\n", encoding="utf-8")
            spec = TaskSpec(user_query="script", allowed_tools=["script_runner"], input_data={"workspace_base_dir": tmp})

            result = call_tool(
                "script_runner",
                {"command": [sys.executable, str(script)], "required_dependencies": ["definitely_missing_aura_dependency"]},
                spec,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "dependency_missing")
        self.assertIn("definitely_missing_aura_dependency", result["error"])


if __name__ == "__main__":
    unittest.main()
