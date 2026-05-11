import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.execution.runtime_adapter import import_research_os_mvp


ros = import_research_os_mvp()


class ResearchOSProjectMemoryClearTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_project_memory_clear_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"title": "Memory Clear Demo", "research_area": "BV2"})
        self.project_id = self.project["id"]
        uploaded = ros.register_file(self.agent_root, {"project_id": self.project_id, "filename": "data.csv", "content": "group,value\nA,1"})
        ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project_id,
                "title": "Memory clear reference",
                "abstract": "A reference that must survive memory clearing.",
                "full_text": "Reference content.",
                "full_text_path": uploaded["stored_path"],
                "source_provider": "unit",
            },
        )
        ros.create_agent_memory_entry(
            self.agent_root,
            {
                "memory_scope": "project",
                "project_id": self.project_id,
                "memory_type": "project_decision",
                "title": "Memory to clear",
                "content": "This project memory should be deleted.",
            },
        )
        ros.create_literature_search_task(self.agent_root, {"project_id": self.project_id, "query": "BV2", "status": "running"})

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clear_project_memory_scope_preserves_non_memory_content(self) -> None:
        before = ros.get_project_status(self.agent_root, self.project_id)["counts"]
        plan = ros.clear_project(self.agent_root, self.project_id, "memory", dry_run=True)["deletion_plan"]

        result = ros.clear_project(self.agent_root, self.project_id, "memory", confirmation=plan["confirmation_phrase"])
        after = ros.get_project_status(self.agent_root, self.project_id)["counts"]

        self.assertTrue(result["executed"])
        self.assertGreater(before["project_memory"], 0)
        self.assertEqual(after["project_memory"], 0)
        self.assertEqual(after["uploaded_files"], before["uploaded_files"])
        self.assertEqual(after["kb_records"], before["kb_records"])
        self.assertEqual(after["task_records"], before["task_records"])


if __name__ == "__main__":
    unittest.main()
