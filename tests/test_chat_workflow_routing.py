import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from backend.researchos.integration.workflow_execution_service import WorkflowExecutionService


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class ChatWorkflowRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_chat_route_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"id": "chat-route", "title": "Chat Route"})

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ppt_route_requests_file_when_material_is_missing(self) -> None:
        result = WorkflowExecutionService(self.agent_root).route_chat(self.project["id"], "帮我把这篇论文做成组会 PPT")

        self.assertEqual(result["intent"], "nature_paper_to_ppt")
        self.assertEqual(result["status"], "needs_file")

    def test_polish_route_is_ready_with_chat_text(self) -> None:
        result = WorkflowExecutionService(self.agent_root).route_chat(self.project["id"], "帮我润色摘要：The supplied abstract.")

        self.assertEqual(result["intent"], "nature_academic_polishing")
        self.assertEqual(result["status"], "plan_only")


if __name__ == "__main__":
    unittest.main()
