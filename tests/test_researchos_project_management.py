import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class ResearchOSProjectManagementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_project_mgmt_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"title": "Project Ops Demo", "research_area": "BV2 CCK8"})
        self.project_id = self.project["id"]
        self._seed_project_content()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed_project_content(self) -> None:
        ros.register_file(self.agent_root, {"project_id": self.project_id, "filename": "BV2 CCK8 251115.xlsx", "content": "group,od\ncontrol,0.5\nLPS,0.3"})
        pdf = ros.register_file(self.agent_root, {"project_id": self.project_id, "filename": "downloaded-paper.pdf", "content": "paper pdf text", "source": "downloaded", "category": "paper"})
        reference = ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project_id,
                "title": "BV2 CCK8 reference",
                "abstract": "BV2 viability CCK8 assay.",
                "full_text": "BV2 cells were measured by CCK8.",
                "full_text_path": pdf["stored_path"],
                "source_provider": "unit",
                "access_status": "downloaded",
            },
        )
        ros.build_project_research_kb(self.agent_root, {"project_id": self.project_id, "reference_ids": [reference["id"]], "include_article_analysis": False})
        ros.create_agent_memory_entry(
            self.agent_root,
            {
                "memory_scope": "project",
                "project_id": self.project_id,
                "memory_type": "project_decision",
                "title": "Use CCK8",
                "content": "Use CCK8 as a viability screen.",
            },
        )
        ros.create_literature_search_task(self.agent_root, {"project_id": self.project_id, "query": "BV2 CCK8", "keywords": ["BV2", "CCK8"], "status": "running"})
        ros.start_service_skill_run(self.agent_root, "unit_skill", "UnitSkill", self.project_id, {"project_id": self.project_id})

    def test_archive_project_preserves_files_and_memory(self) -> None:
        before_files = len(ros.list_recent_uploaded_files(self.agent_root, self.project_id, limit=20))
        before_memory = len(ros.list_agent_memory(self.agent_root, project_id=self.project_id)["entries"])

        archived = ros.archive_project(self.agent_root, self.project_id)

        self.assertEqual(archived["status"], "archived")
        self.assertFalse(archived["is_active"])
        self.assertEqual(len(ros.list_recent_uploaded_files(self.agent_root, self.project_id, limit=20)), before_files)
        self.assertEqual(len(ros.list_agent_memory(self.agent_root, project_id=self.project_id)["entries"]), before_memory)

    def test_unarchive_project_restores_active_status(self) -> None:
        ros.archive_project(self.agent_root, self.project_id)

        restored = ros.unarchive_project(self.agent_root, self.project_id)

        self.assertEqual(restored["status"], "active")
        self.assertTrue(restored["is_active"])

    def test_clear_project_all_dry_run_returns_plan_without_deleting(self) -> None:
        before = ros.get_project_status(self.agent_root, self.project_id)

        result = ros.clear_project(self.agent_root, self.project_id, "all", dry_run=True)
        after = ros.get_project_status(self.agent_root, self.project_id)

        self.assertFalse(result["executed"])
        self.assertIn("deletion_plan", result)
        self.assertGreater(result["deletion_plan"]["record_count"], 0)
        self.assertEqual(after["counts"], before["counts"])

    def test_clear_project_all_with_confirmation_preserves_project_shell(self) -> None:
        result = ros.clear_project(
            self.agent_root,
            self.project_id,
            "all",
            confirmation="确认清空 Project Ops Demo",
        )
        status = ros.get_project_status(self.agent_root, self.project_id)

        self.assertTrue(result["executed"])
        self.assertEqual(status["display_name"], "Project Ops Demo")
        self.assertEqual(status["counts"]["uploaded_files"], 0)
        self.assertEqual(status["counts"]["kb_records"], 0)
        self.assertEqual(status["counts"]["project_memory"], 0)
        self.assertEqual(status["counts"]["task_records"], 0)
        self.assertEqual(status["counts"]["data_contexts"], 0)

    def test_purge_project_without_confirmation_does_not_execute(self) -> None:
        result = ros.purge_project(self.agent_root, self.project_id)

        self.assertFalse(result["executed"])
        self.assertIn("deletion_plan", result)
        self.assertEqual(ros.get_project_status(self.agent_root, self.project_id)["status"], "active")

    def test_purge_project_with_confirmation_marks_project_purged_and_hides_from_default_list(self) -> None:
        result = ros.purge_project(
            self.agent_root,
            self.project_id,
            confirmation="CONFIRM PURGE Project Ops Demo",
            confirmed_by_user="unit-test",
        )

        self.assertTrue(result["executed"])
        self.assertEqual(ros.get_project_status(self.agent_root, self.project_id)["status"], "purged")
        grouped = ros.list_projects_grouped(self.agent_root)
        self.assertFalse(any(item["display_name"] == "Project Ops Demo" for item in grouped["active"] + grouped["archived"]))

    def test_delete_failure_returns_failed_files(self) -> None:
        with patch("pathlib.Path.unlink", side_effect=PermissionError("locked")):
            result = ros.clear_project(
                self.agent_root,
                self.project_id,
                "uploads",
                confirmation="确认清空 Project Ops Demo",
            )

        self.assertFalse(result["executed"])
        self.assertTrue(result["failed_files"])

    def test_project_operation_answers_use_display_name_not_project_id(self) -> None:
        archive_answer = ros.format_project_archive_answer(ros.archive_project(self.agent_root, self.project_id))
        status_answer = ros.format_project_management_status_answer(ros.get_project_status(self.agent_root, self.project_id))

        self.assertIn("Project Ops Demo", archive_answer)
        self.assertIn("Project Ops Demo", status_answer)
        self.assertNotIn(self.project_id, archive_answer)
        self.assertNotIn(self.project_id, status_answer)


if __name__ == "__main__":
    unittest.main()
