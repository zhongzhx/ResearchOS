import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from backend.researchos.execution.coding_runtime import CodingRuntimeService


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class CodingRuntimeSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_coding_security_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"id": "coding-security", "title": "Coding Security"})
        self.runtime = CodingRuntimeService(self.agent_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_workspace_uses_project_scoped_directories(self) -> None:
        paths = self.runtime.create_run_workspace(self.project["id"], "run-security")
        root = self.agent_root / "projects" / self.project["id"] / "runs" / "run-security"
        self.assertEqual(paths["run_root"], root)
        self.assertEqual(paths["workspace"], root / "workspace")
        self.assertEqual(paths["outputs"], root / "outputs")
        self.assertEqual(paths["logs"], root / "logs")

    def test_output_path_traversal_is_rejected(self) -> None:
        paths = self.runtime.create_run_workspace(self.project["id"], "run-escape")
        with self.assertRaisesRegex(ValueError, "output path escapes"):
            self.runtime.resolve_output_path(paths, "../escape.txt")

    def test_unknown_template_returns_failed(self) -> None:
        result = self.runtime.execute_template(self.project["id"], "missing-template", {})
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "failed")

    def test_undeclared_input_file_is_rejected(self) -> None:
        outside = self.tmp / "outside.csv"
        outside.write_text("group,value\nA,1\n", encoding="utf-8")

        result = self.runtime.execute_template(self.project["id"], "data_profile", {"input_file": str(outside)})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "needs_input")
        self.assertIn("artifact registry or declared", result["user_message"])

    def test_python_argv_path_escape_is_rejected(self) -> None:
        paths = self.runtime.create_run_workspace(self.project["id"], "argv-escape")
        script = paths["workspace"] / "run.py"
        script.write_text("print('ok')\n", encoding="utf-8")

        result = self.runtime.execute_python_argv(
            self.project["id"],
            [sys.executable, str(script), str(self.tmp / "outside.csv")],
            run_id="argv-escape",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("escapes", result["user_message"])


if __name__ == "__main__":
    unittest.main()
