import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_context_compiler as compiler  # noqa: E402
import research_os_mvp as ros  # noqa: E402


class ResearchOSMemorySourceOfTruthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_memory_truth_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(
            self.agent_root,
            {"title": "Memory Truth Project", "research_area": "source of truth rules"},
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _insert_legacy_agent_memory_conflict(self, text: str) -> None:
        conn = sqlite3.connect(self.agent_root / "agent_memory.sqlite")
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_ledger (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    memory_type TEXT,
                    subject TEXT,
                    content TEXT,
                    status TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO memory_ledger(id, project_id, memory_type, subject, content, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("legacy-conflict-memory", self.project["id"], "project_note", "Canonical dose", text, "active", ros.now(), ros.now()),
            )
            conn.commit()
        finally:
            conn.close()

    def _insert_lab_rag_conflict(self, text: str) -> None:
        conn = sqlite3.connect(self.agent_root / "lab_agent_mvp.sqlite")
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id TEXT PRIMARY KEY,
                    file_id TEXT,
                    file_name TEXT,
                    source_type TEXT,
                    chunk_text TEXT,
                    metadata_json TEXT,
                    embedding_json TEXT,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO document_chunks(id, file_id, file_name, source_type, chunk_text, metadata_json, embedding_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("lab-conflict-chunk", "legacy-file", "legacy.pdf", "legacy_lab_rag", text, "{}", "[]", ros.now()),
            )
            conn.commit()
        finally:
            conn.close()

    def test_memory_backend_registry_declares_primary_and_derived_backends(self) -> None:
        registry = ros.list_memory_backend_registry(self.agent_root)
        by_class_backend = {(item["memory_class"], item["backend_name"]): item for item in registry}

        for memory_class in [
            "projects",
            "tasks",
            "chat",
            "agent_memory_entries",
            "references",
            "reference_chunks",
            "knowledge_base_entries",
        ]:
            row = by_class_backend[(memory_class, "research_group_os.sqlite")]
            self.assertEqual(row["owner"], "research_os_mvp")
            self.assertEqual(row["source_of_truth"], 1)
            self.assertEqual(row["sync_policy"], "authoritative_write_read")

        derived_backends = {
            ("agent_memory_compat", "agent_memory.sqlite"),
            ("lab_rag_legacy", "lab_agent_mvp.sqlite"),
            ("managed_memory_skill_files", "manage-agent-memory folder"),
            ("brain_markdown_repo", "backend/researchos/brain"),
        }
        for key in derived_backends:
            row = by_class_backend[key]
            self.assertEqual(row["source_of_truth"], 0)
            self.assertIn("research_group_os.sqlite", row["derived_from"])

    def test_context_compiler_prefers_main_memory_when_derived_backends_conflict(self) -> None:
        primary_text = "Primary source says the canonical dose is 10 nM."
        derived_text = "Derived conflict says the canonical dose is 999 nM."
        ros.create_agent_memory_entry(
            self.agent_root,
            {
                "memory_scope": "project",
                "project_id": self.project["id"],
                "memory_type": "project_note",
                "title": "Canonical dose",
                "content": primary_text,
            },
        )
        self._insert_legacy_agent_memory_conflict(derived_text)
        self._insert_lab_rag_conflict(derived_text)

        context = compiler.compile_research_context(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "user_message": "What is the canonical dose?",
                "intent": "research_advice",
            },
        )
        rendered = context["compiled_context"]
        agent_memory_items = [item for item in context["context_items"] if item.get("source_type") == "agent_memory"]

        self.assertIn(primary_text, rendered)
        self.assertNotIn(derived_text, rendered)
        self.assertTrue(agent_memory_items)
        self.assertTrue(all(item.get("metadata", {}).get("source_of_truth") == "research_group_os.sqlite" for item in agent_memory_items))
        self.assertTrue(all(item.get("metadata", {}).get("source_role") == "primary" for item in agent_memory_items))

    def test_rag_project_memory_prefers_main_memory_over_derived_backends(self) -> None:
        primary_text = "Primary source says the canonical dose is 10 nM."
        derived_text = "Derived conflict says the canonical dose is 999 nM."
        ros.create_agent_memory_entry(
            self.agent_root,
            {
                "memory_scope": "project",
                "project_id": self.project["id"],
                "memory_type": "project_note",
                "title": "Canonical dose",
                "content": primary_text,
            },
        )
        self._insert_legacy_agent_memory_conflict(derived_text)
        self._insert_lab_rag_conflict(derived_text)

        result = ros.query_research_rag(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "question": "What is the canonical dose?",
                "mode": "project_memory_only",
            },
        )
        rendered = json.dumps(result, ensure_ascii=False)

        self.assertIn(primary_text, rendered)
        self.assertNotIn(derived_text, rendered)
        self.assertTrue(result["retrieved_chunks"])
        self.assertEqual({item["source_type"] for item in result["retrieved_chunks"]}, {"agent_memory"})

    def test_derived_backends_missing_do_not_block_main_context_or_health(self) -> None:
        if (self.agent_root / "agent_memory.sqlite").exists():
            (self.agent_root / "agent_memory.sqlite").unlink()
        if (self.agent_root / "lab_agent_mvp.sqlite").exists():
            (self.agent_root / "lab_agent_mvp.sqlite").unlink()
        primary_text = "Primary only memory remains available."
        ros.create_agent_memory_entry(
            self.agent_root,
            {
                "memory_scope": "project",
                "project_id": self.project["id"],
                "memory_type": "project_note",
                "title": "Primary only",
                "content": primary_text,
            },
        )

        context = compiler.compile_research_context(
            self.agent_root,
            {"project_id": self.project["id"], "user_message": "primary only", "intent": "research_advice"},
        )
        health = ros.get_memory_source_of_truth_health(self.agent_root, self.project["id"])

        self.assertIn(primary_text, context["compiled_context"])
        self.assertEqual(health["status"], "ok")
        self.assertTrue(health["checks"]["main_context_retrieval"]["ok"])
        self.assertTrue(health["checks"]["derived_missing_does_not_block"]["ok"])

    def test_memory_architecture_doc_exists_and_names_backend_boundaries(self) -> None:
        doc = ROOT / "MEMORY_ARCHITECTURE.md"

        self.assertTrue(doc.exists())
        text = doc.read_text(encoding="utf-8")
        for expected in [
            "research_group_os.sqlite",
            "agent_memory.sqlite",
            "lab_agent_mvp.sqlite",
            "manage-agent-memory",
            "backend/researchos/brain",
            "source of truth",
        ]:
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
