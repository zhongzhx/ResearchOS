import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "research-agent-runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402
from backend.researchos.brain.workflow_template_builder import build_workflow_template_from_skillruns, detect_repeated_workflow_patterns, list_workflow_templates, save_workflow_template  # noqa: E402


class WorkflowTemplateBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_workflow_template_"))
        self.agent_root = self.tmp / "agent_data"
        self.brain_root = self.tmp / "research_brain"
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.agent_root)
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.brain_root)
        self.project = ros.create_project(self.agent_root, {"title": "Workflow", "research_area": "test"})

    def tearDown(self) -> None:
        os.environ.pop("RESEARCHOS_AGENT_ROOT", None)
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_template_from_multiple_successful_skillruns(self) -> None:
        ids = []
        for i in range(2):
            run = ros.start_service_skill_run(self.agent_root, f"core_test_{i}", "Report Writer", self.project["id"], {"task_type": "report_generation"})
            ros.update_skill_run(self.agent_root, run["id"], status="completed", output_payload={"ok": True}, output_object_refs=[], logs=[])
            ids.append(run["id"])

        patterns = detect_repeated_workflow_patterns(self.project["id"])
        template = build_workflow_template_from_skillruns(ids)
        saved = save_workflow_template(template)

        self.assertTrue(patterns)
        self.assertEqual(saved["status"], "pending_review")
        self.assertTrue(list_workflow_templates(self.project["id"]))


if __name__ == "__main__":
    unittest.main()
