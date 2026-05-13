import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import rag_retrieval_service as rag  # noqa: E402
import research_context_compiler as compiler  # noqa: E402
import research_os_mvp as ros  # noqa: E402
from backend.researchos.brain.brain_page import create_brain_page  # noqa: E402


class UnifiedRAGServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_unified_rag_"))
        self.agent_root = self.tmp / "agent_data"
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        self.project = ros.create_project(
            self.agent_root,
            {"title": "Unified RAG Project", "research_area": "macrophage inflammation"},
        )
        self.reference = ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "RAW264.7 mitochondrial inflammation paper",
                "authors": ["Unit Tester"],
                "year": "2026",
                "doi": "10.0000/unified-rag",
                "source_provider": "pubmed",
                "evidence_level": "peer_reviewed_full_text",
                "full_text": "RAW264.7 macrophage inflammation depends on mitochondrial ROS and NF-kB signaling.",
            },
        )
        ros.build_project_research_kb(
            self.agent_root,
            {"project_id": self.project["id"], "reference_ids": [self.reference["id"]], "include_article_analysis": False},
        )
        ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "Browser note about RAW264.7",
                "source_provider": "browser/manual",
                "source_type": "browser_learning",
                "evidence_level": "browser_learning_not_evidence",
                "full_text": "BROWSER_LEARNING_NOT_PEER_REVIEWED says RAW264.7 browser note mentions mitochondria.",
            },
        )
        ros.create_agent_memory_entry(
            self.agent_root,
            {
                "memory_scope": "project",
                "project_id": self.project["id"],
                "memory_type": "project_note",
                "title": "Canonical dose",
                "content": "AGENT_MEMORY_CANONICAL_DOSE says the working dose is 10 nM.",
            },
        )
        self._insert_lab_chunk("LAB_RAG_DOCUMENT_CHUNK says uploaded lab notes mention mitochondrial ROS.")
        self._insert_prior_rag_query("PRIOR_RAG_QUERY_MEMORY says mitochondria was already queried.")
        create_brain_page(
            "claim",
            "unified-rag-brain-note",
            {"title": "Brain note", "project_id": self.project["id"], "confidence": "medium", "source_ids": ["brain-note-1"]},
            "BRAIN_NOTE_MEMORY says RAW264.7 inflammation and mitochondria are linked.",
            [],
        )

    def tearDown(self) -> None:
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _insert_lab_chunk(self, text: str) -> None:
        conn = sqlite3.connect(self.agent_root / "lab_agent_mvp.sqlite")
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    file_id TEXT PRIMARY KEY,
                    project_name TEXT,
                    file_name TEXT,
                    source_type TEXT,
                    source_path TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id TEXT PRIMARY KEY,
                    file_id TEXT,
                    file_name TEXT,
                    source_type TEXT,
                    chunk_text TEXT,
                    metadata_json TEXT,
                    embedding_json TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "INSERT INTO documents(file_id, project_name, file_name, source_type, source_path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("lab-file-1", self.project["title"], "lab-note.pdf", "lab_note", "", ros.now()),
            )
            conn.execute(
                "INSERT INTO document_chunks(id, file_id, file_name, source_type, chunk_text, metadata_json, embedding_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("lab-chunk-1", "lab-file-1", "lab-note.pdf", "lab_note", text, json.dumps({"page_number": 1}), "[]", ros.now()),
            )
            conn.commit()
        finally:
            conn.close()

    def _insert_prior_rag_query(self, answer: str) -> None:
        conn = ros.connect(self.agent_root)
        try:
            conn.execute(
                """
                INSERT INTO rag_queries(id, project_id, question, answer, retrieved_chunk_ids_json, citation_map_json, skill_run_id, created_at, mode, limitations_json, source_breakdown_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("prior-rag-query-1", self.project["id"], "mitochondria", answer, "[]", "{}", "", ros.now(), "agent_chat", "[]", "{}"),
            )
            conn.commit()
        finally:
            conn.close()

    def test_unified_rag_query_normalizes_all_supported_source_types(self) -> None:
        result = rag.unified_rag_query(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "question": "RAW264.7 mitochondria inflammation canonical dose browser lab brain prior",
                "mode": "all_project_context",
                "limit": 12,
            },
        )

        source_types = {item["source_type"] for item in result["results"]}
        self.assertIn("reference_chunk", source_types)
        self.assertIn("kb_entry", source_types)
        self.assertIn("browser_learning", source_types)
        self.assertIn("agent_memory", source_types)
        self.assertIn("brain_note", source_types)
        self.assertTrue(source_types.issubset({"reference_chunk", "kb_entry", "browser_learning", "brain_note", "agent_memory", "task_status"}))
        for item in result["results"]:
            self.assertIn("citation_id", item)
            self.assertIn("can_support_peer_reviewed_evidence", item)
            self.assertIn("source_type", item)

    def test_same_reference_uses_one_citation_id_for_chunk_and_kb_summary(self) -> None:
        result = rag.unified_rag_query(
            self.agent_root,
            {"project_id": self.project["id"], "question": "RAW264.7 mitochondrial ROS NF-kB", "limit": 10},
        )
        same_reference = [
            item
            for item in result["results"]
            if item.get("reference_id") == self.reference["id"] and item["source_type"] in {"reference_chunk", "kb_entry"}
        ]

        self.assertGreaterEqual({item["source_type"] for item in same_reference}, {"reference_chunk", "kb_entry"})
        self.assertEqual({item["citation_id"] for item in same_reference}, {"[1]"})

    def test_browser_learning_is_not_peer_reviewed_evidence_by_default(self) -> None:
        result = rag.unified_rag_query(
            self.agent_root,
            {"project_id": self.project["id"], "question": "BROWSER_LEARNING_NOT_PEER_REVIEWED mitochondria", "limit": 10},
        )
        browser_items = [item for item in result["results"] if item["source_type"] == "browser_learning"]

        self.assertTrue(browser_items)
        self.assertTrue(all(item["can_support_peer_reviewed_evidence"] is False for item in browser_items))
        self.assertTrue(all(item["evidence_role"] == "browser_learning" for item in browser_items))

    def test_main_rag_entry_uses_unified_result_contract(self) -> None:
        direct = rag.unified_rag_query(
            self.agent_root,
            {"project_id": self.project["id"], "question": "RAW264.7 mitochondrial ROS", "limit": 8},
        )
        main = ros.query_research_rag(
            self.agent_root,
            {"project_id": self.project["id"], "question": "RAW264.7 mitochondrial ROS", "limit": 8},
        )

        self.assertEqual(main["retrieval_service"], "unified_rag_query")
        self.assertEqual(
            [{k: item.get(k) for k in ["source_type", "citation_id", "reference_id"]} for item in main["retrieved_chunks"][:5]],
            [{k: item.get(k) for k in ["source_type", "citation_id", "reference_id"]} for item in direct["results"][:5]],
        )

    def test_context_compiler_uses_unified_rag_source_types(self) -> None:
        context = compiler.compile_research_context(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "user_message": "RAW264.7 mitochondrial ROS",
                "intent": "kb_query",
            },
        )
        source_types = {item["source_type"] for item in context["context_items"]}

        self.assertIn("reference_chunk", source_types)
        self.assertIn("kb_entry", source_types)
        self.assertNotIn("rag_chunk", source_types)


if __name__ == "__main__":
    unittest.main()
