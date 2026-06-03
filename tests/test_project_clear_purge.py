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
from agent_memory import api as memory_api  # noqa: E402
from agent_memory.database import connect as connect_agent_memory  # noqa: E402


class ProjectClearPurgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_clear_purge_"))
        self.original_env = {key: os.environ.get(key) for key in ["MEMORYOS_ROOT", "RESEARCH_BRAIN_ROOT"]}
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        self.agent_root = self.tmp / "agent_root"
        self.project = ros.create_project(self.agent_root, {"id": "clear-me", "title": "Clear Me"})
        self.project_id = self.project["id"]
        self.survivor = ros.create_project(self.agent_root, {"id": "keep-me", "title": "Keep Me"})
        ros.register_file(self.agent_root, {"project_id": self.project_id, "filename": "input.csv", "content": "a,b\n1,2"})
        ros.archive_project_artifact(
            self.agent_root,
            {"project_id": self.project_id, "filename": "result.md", "content": "# Result", "artifact_type": "markdown"},
        )
        session = ros.ensure_chat_session(self.agent_root, self.project_id, "clear-chat")
        ros.save_chat_message(self.agent_root, session["id"], "user", "clear this", {}, project_id=self.project_id)
        memory_api.create_memory(self.agent_root, {"project_id": self.project_id, "memory_type": "task_memory", "subject": "delete", "content": "delete me"})
        memory_api.create_memory(self.agent_root, {"project_id": self.survivor["id"], "memory_type": "task_memory", "subject": "keep", "content": "keep me"})
        conn = connect_agent_memory(self.agent_root)
        try:
            self.survivor_memory_count = conn.execute("SELECT COUNT(*) FROM memory_ledger WHERE project_id=?", (self.survivor["id"],)).fetchone()[0]
        finally:
            conn.close()
        self.project_memoryos_dir = self.tmp / "memoryos" / "semantic" / self.project_id
        self.survivor_memoryos_dir = self.tmp / "memoryos" / "semantic" / self.survivor["id"]
        self.project_brain_dir = self.tmp / "research_brain" / "projects" / self.project_id
        self.survivor_brain_dir = self.tmp / "research_brain" / "projects" / self.survivor["id"]
        for path in [self.project_memoryos_dir, self.survivor_memoryos_dir, self.project_brain_dir, self.survivor_brain_dir]:
            path.mkdir(parents=True, exist_ok=True)
            (path / "cache.json").write_text('{"cached": true}', encoding="utf-8")

    def tearDown(self) -> None:
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def assert_derived_cache_removed_for_target_only(self) -> None:
        self.assertFalse(self.project_memoryos_dir.exists())
        self.assertFalse(self.project_brain_dir.exists())
        self.assertTrue(self.survivor_memoryos_dir.is_dir())
        self.assertTrue(self.survivor_brain_dir.is_dir())
        conn = connect_agent_memory(self.agent_root)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM memory_ledger WHERE project_id=?", (self.project_id,)).fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM memory_ledger WHERE project_id=?", (self.survivor["id"],)).fetchone()[0], self.survivor_memory_count)
        finally:
            conn.close()

    def test_clear_removes_runtime_data_but_recreates_project_shell(self) -> None:
        plan = ros.clear_project(self.agent_root, self.project_id, "all", dry_run=True)["deletion_plan"]

        result = ros.clear_project(self.agent_root, self.project_id, "all", confirmation=plan["confirmation_phrase"])
        status = ros.get_project_status(self.agent_root, self.project_id)

        self.assertTrue(result["executed"])
        self.assertTrue(Path(self.project["root_dir"]).is_dir())
        self.assertTrue(Path(status["manifest_path"]).is_file())
        self.assertEqual(ros.list_files(self.agent_root, self.project_id), [])
        self.assertEqual(ros.list_project_artifacts(self.agent_root, self.project_id), [])
        self.assert_derived_cache_removed_for_target_only()
        conn = ros.connect(self.agent_root)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM chat_sessions WHERE project_id=?", (self.project_id,)).fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0], 0)
        finally:
            conn.close()

    def test_purge_requires_boolean_confirmation_and_deletes_project_row(self) -> None:
        plan = ros.purge_project(self.agent_root, self.project_id, dry_run=True)["deletion_plan"]

        refused = ros.purge_project(self.agent_root, self.project_id, confirmation=plan["confirmation_phrase"])
        self.assertFalse(refused["executed"])
        self.assertEqual(refused["reason"], "confirm_true_required")

        result = ros.purge_project(self.agent_root, self.project_id, confirmation=plan["confirmation_phrase"], confirm=True)

        self.assertTrue(result["executed"])
        self.assertFalse(Path(self.project["root_dir"]).exists())
        self.assert_derived_cache_removed_for_target_only()
        with self.assertRaisesRegex(KeyError, "project not found"):
            ros.get_project_detail(self.agent_root, self.project_id)
        conn = ros.connect(self.agent_root)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM project_purge_audit WHERE project_id=?", (self.project_id,)).fetchone()[0], 1)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
