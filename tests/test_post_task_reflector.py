import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402
from backend.researchos.brain.post_task_reflector import reflect_on_completed_skillrun  # noqa: E402


class PostTaskReflectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_reflector_"))
        self.agent_root = self.tmp / "agent_data"
        self.brain_root = self.tmp / "research_brain"
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.agent_root)
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.brain_root)
        self.project = ros.create_project(self.agent_root, {"title": "Reflector", "research_area": "test"})

    def tearDown(self) -> None:
        os.environ.pop("RESEARCHOS_AGENT_ROOT", None)
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _skillrun(self, status: str = "completed") -> str:
        run = ros.start_service_skill_run(self.agent_root, "core_report_writer", "Report Writer", self.project["id"], {"task_type": "report_generation", "user_query": "write report"})
        ros.update_skill_run(
            self.agent_root,
            run["id"],
            status=status,
            output_payload={"structured_outputs": {"report": "ok"}, "output_files": ["report.md"]} if status == "completed" else {"error": "boom"},
            output_object_refs=[{"type": "report", "id": "report-1"}] if status == "completed" else [],
            logs=["tool:file_writer", "completed"] if status == "completed" else ["failed"],
        )
        return run["id"]

    def test_completed_successful_skillrun_triggers_reflection(self) -> None:
        skillrun_id = self._skillrun("completed")

        reflection = reflect_on_completed_skillrun(skillrun_id)

        self.assertTrue(reflection["should_update_brain"])
        self.assertTrue(reflection["should_crystallize_skill"])
        self.assertGreaterEqual(reflection["reuse_score"], 0.7)
        self.assertTrue((self.brain_root / "workflows" / "reflections" / f"{skillrun_id}.json").exists())

    def test_failed_skillrun_does_not_crystallize_skill(self) -> None:
        skillrun_id = self._skillrun("failed")

        reflection = reflect_on_completed_skillrun(skillrun_id)

        self.assertTrue(reflection["should_update_brain"])
        self.assertFalse(reflection["should_crystallize_skill"])
        self.assertIn("failure", reflection["memory_targets"])


if __name__ == "__main__":
    unittest.main()
