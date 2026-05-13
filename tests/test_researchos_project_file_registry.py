import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class ResearchOSProjectFileRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_project_file_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(
            self.agent_root,
            {"title": "BV2 CCK8 Project", "research_area": "BV2 inflammatory viability"},
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def chat(self, message: str) -> dict:
        return ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": message})

    def test_file_path_question_routes_to_file_registry_query(self) -> None:
        message = "\u6211\u4e0a\u4f20\u7684\u6587\u4ef6\u4f60\u7684\u4fdd\u5b58\u8def\u5f84\u662f\uff1f"

        self.assertEqual(ros.classify_research_intent(message), "file_registry_query")
        self.assertEqual(ros.infer_agent_intent(message), "file_registry_query")

    def test_uploaded_xlsx_registers_file_registry_fields(self) -> None:
        file_record = ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "original_filename": "BV2 CCK8 251115.xlsx",
                "content": "group,od\ncontrol,0.52\nLPS,0.31\n",
            },
        )

        self.assertEqual(file_record["original_filename"], "BV2 CCK8 251115.xlsx")
        self.assertEqual(file_record["project_id"], self.project["id"])
        self.assertTrue(file_record["stored_path"])
        self.assertIn(file_record["parse_status"], {"not_parsed", "parsed", "partial", "failed"})

    def test_file_path_answer_uses_filename_and_display_name_without_project_id(self) -> None:
        ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "original_filename": "BV2 CCK8 251115.xlsx",
                "content": "group,od\ncontrol,0.52\nLPS,0.31\n",
            },
        )

        response = self.chat("\u521a\u624d\u4e0a\u4f20\u7684 xlsx \u5728\u54ea\u91cc")

        self.assertEqual(response["intent"], "file_registry_query")
        self.assertIn("BV2 CCK8 251115.xlsx", response["answer"])
        self.assertIn("BV2 CCK8 Project", response["answer"])
        self.assertIn("parse_status", response["answer"])
        self.assertNotIn(self.project["id"], response["answer"])

    def test_parse_table_message_routes_to_uploaded_file_parse(self) -> None:
        self.assertEqual(ros.classify_research_intent("\u89e3\u6790\u5b9e\u9a8c\u8868\u683c"), "uploaded_file_parse")
        self.assertEqual(ros.infer_agent_intent("\u89e3\u6790\u5b9e\u9a8c\u8868\u683c"), "uploaded_file_parse")

    def test_project_ui_views_use_display_name_without_internal_id(self) -> None:
        projects = ros.list_projects_for_ui(self.agent_root)
        state = ros.workspace_state(self.agent_root, self.project["id"])
        response = self.chat("\u5f53\u524d\u9879\u76ee\u662f\u4ec0\u4e48")

        self.assertEqual(projects[0]["display_name"], "BV2 CCK8 Project")
        self.assertNotIn("id", projects[0])
        self.assertEqual(state["active_project_display_name"], "BV2 CCK8 Project")
        self.assertEqual(response["intent"], "project_status")
        self.assertIn("BV2 CCK8 Project", response["answer"])
        self.assertNotIn(self.project["id"], response["answer"])


if __name__ == "__main__":
    unittest.main()
