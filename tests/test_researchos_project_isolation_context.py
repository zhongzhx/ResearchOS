import shutil
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


class ResearchOSProjectIsolationContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_project_isolation_"))
        self.agent_root = self.tmp / "agent_data"
        self.project_a = ros.create_project(
            self.agent_root,
            {"title": "Alpha Macrophage", "aliases": ["alpha", "巨噬细胞课题"], "research_area": "alpha biology"},
        )
        self.project_b = ros.create_project(
            self.agent_root,
            {"title": "Beta Organoid", "aliases": ["beta", "类器官"], "research_area": "beta biology"},
        )
        self.archived = ros.create_project(
            self.agent_root,
            {"title": "Archived Gamma", "aliases": ["gamma"], "research_area": "gamma biology", "status": "archived"},
        )
        self._seed_project(self.project_a["id"], "alpha-file.csv", "alpha cytokine evidence", "Alpha memory")
        self._seed_project(self.project_b["id"], "beta-file.csv", "beta organoid evidence", "Beta memory")
        self._seed_project(self.archived["id"], "gamma-file.csv", "gamma archived evidence", "Gamma memory")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed_project(self, project_id: str, filename: str, evidence: str, memory_title: str) -> None:
        ros.register_file(self.agent_root, {"project_id": project_id, "filename": filename, "content": evidence})
        reference = ros.import_reference(
            self.agent_root,
            {
                "project_id": project_id,
                "title": evidence,
                "abstract": evidence,
                "full_text": evidence,
                "source_provider": "unit",
                "access_status": "downloaded",
            },
        )
        ros.build_project_research_kb(
            self.agent_root,
            {"project_id": project_id, "reference_ids": [reference["id"]], "include_article_analysis": False},
        )
        ros.create_agent_memory_entry(
            self.agent_root,
            {
                "memory_scope": "project",
                "project_id": project_id,
                "memory_type": "project_note",
                "title": memory_title,
                "content": evidence,
            },
        )

    def test_rag_defaults_to_active_project_and_cross_project_requires_explicit_scope(self) -> None:
        default_result = ros.query_research_rag(
            self.agent_root,
            {"project_id": self.project_a["id"], "question": "beta organoid"},
        )
        self.assertEqual(default_result["retrieval_scope"], "current_project")
        self.assertFalse(default_result["retrieved_chunks"])

        cross_result = ros.query_research_rag(
            self.agent_root,
            {"project_id": self.project_a["id"], "question": "beta organoid", "retrieval_scope": "cross_project"},
        )
        self.assertEqual(cross_result["retrieval_scope"], "cross_project")
        self.assertTrue(cross_result["retrieved_chunks"])
        self.assertEqual({chunk["project_id"] for chunk in cross_result["retrieved_chunks"]}, {self.project_b["id"]})

    def test_agent_memory_and_data_context_default_to_current_project(self) -> None:
        memory = ros.list_agent_memory(self.agent_root, project_id=self.project_a["id"])
        data_contexts = ros.list_data_contexts(self.agent_root, project_id=self.project_a["id"])

        self.assertEqual({entry["project_id"] for entry in memory["entries"]}, {self.project_a["id"]})
        self.assertEqual({context["project_id"] for context in data_contexts}, {self.project_a["id"]})

    def test_library_reads_require_a_project_scope(self) -> None:
        ros.create_paper_request(
            self.agent_root,
            {"project_id": self.project_a["id"], "title": "Alpha manual paper", "reason": "manual download"},
        )

        for reader in [
            ros.list_files,
            ros.list_references,
            ros.list_knowledge_base_entries,
            ros.list_paper_requests,
        ]:
            with self.subTest(reader=reader.__name__):
                with self.assertRaisesRegex(ValueError, "project_id is required"):
                    reader(self.agent_root)

        self.assertEqual({item["project_id"] for item in ros.list_files(self.agent_root, self.project_a["id"])}, {self.project_a["id"]})
        self.assertEqual({item["project_id"] for item in ros.list_references(self.agent_root, self.project_a["id"])}, {self.project_a["id"]})
        self.assertEqual({item["project_id"] for item in ros.list_knowledge_base_entries(self.agent_root, self.project_a["id"])}, {self.project_a["id"]})
        self.assertEqual({item["project_id"] for item in ros.list_paper_requests(self.agent_root, self.project_a["id"])}, {self.project_a["id"]})

    def test_archived_project_is_not_in_active_retrieval_context(self) -> None:
        state = ros.workspace_state(self.agent_root, self.project_a["id"])
        candidates = state["workspace_diagnostics"]["possible_misassigned_literature"]

        self.assertFalse(any(item["project_id"] == self.archived["id"] for item in candidates))

    def test_project_switch_matches_display_name_and_aliases_and_recompiles_context(self) -> None:
        response = ros.agent_chat(self.agent_root, {"project_id": self.project_a["id"], "message": "切换到 类器官"})

        self.assertEqual(response["intent"], "project_switch")
        self.assertEqual(response["workspace_state"]["active_project_display_name"], "Beta Organoid")
        self.assertEqual(response["compiled_context"]["active_project_display_name"], "Beta Organoid")
        recent_files = response["compiled_context"]["recent_uploaded_files"]
        self.assertEqual([item["original_filename"] for item in recent_files], ["beta-file.csv"])
        self.assertNotIn(self.project_b["id"], response["answer"])

    def test_project_list_uses_display_names_without_internal_ids(self) -> None:
        response = ros.agent_chat(self.agent_root, {"project_id": self.project_a["id"], "message": "有哪些项目"})

        self.assertEqual(response["intent"], "project_list")
        self.assertIn("Alpha Macrophage", response["answer"])
        self.assertIn("Beta Organoid", response["answer"])
        self.assertIn("Archived Gamma", response["answer"])
        self.assertNotIn(self.project_a["id"], response["answer"])
        self.assertNotIn(self.project_b["id"], response["answer"])

    def test_chat_session_can_continue_in_same_project(self) -> None:
        session = ros.ensure_chat_session(self.agent_root, self.project_a["id"], "shared_session", title="Alpha chat")
        same_session = ros.ensure_chat_session(self.agent_root, self.project_a["id"], "shared_session", title="Follow-up")

        ros.save_chat_message(
            self.agent_root,
            session["id"],
            "user",
            "alpha first",
            {"project_id": self.project_a["id"]},
            project_id=self.project_a["id"],
        )
        ros.save_chat_message(
            self.agent_root,
            same_session["id"],
            "assistant",
            "alpha second",
            {"project_id": self.project_a["id"]},
            project_id=self.project_a["id"],
        )
        messages = ros.list_chat_messages(self.agent_root, session["id"], self.project_a["id"], limit=10)

        self.assertEqual(session["id"], same_session["id"])
        self.assertEqual(same_session["project_id"], self.project_a["id"])
        self.assertEqual([item["content"] for item in messages], ["alpha first", "alpha second"])

    def test_chat_session_reuse_across_projects_raises(self) -> None:
        session = ros.ensure_chat_session(self.agent_root, self.project_a["id"], "shared_session", title="Alpha chat")

        with self.assertRaisesRegex(ValueError, "belongs to a different project"):
            ros.ensure_chat_session(self.agent_root, self.project_b["id"], session["id"], title="Beta chat")

        with self.assertRaisesRegex(ValueError, "belongs to a different project"):
            ros.save_chat_message(
                self.agent_root,
                session["id"],
                "user",
                "beta write attempt",
                {"project_id": self.project_b["id"]},
                project_id=self.project_b["id"],
            )

    def test_chat_history_query_requires_matching_project(self) -> None:
        session = ros.ensure_chat_session(self.agent_root, self.project_a["id"], "shared_session", title="Alpha chat")
        ros.save_chat_message(
            self.agent_root,
            session["id"],
            "user",
            "alpha only",
            {"project_id": self.project_a["id"]},
            project_id=self.project_a["id"],
        )

        alpha_messages = ros.list_chat_messages(self.agent_root, session["id"], self.project_a["id"], limit=10)
        beta_messages = ros.list_chat_messages(self.agent_root, session["id"], self.project_b["id"], limit=10)

        self.assertEqual([item["content"] for item in alpha_messages], ["alpha only"])
        self.assertEqual(beta_messages, [])

    def test_context_compiler_exposes_project_scope_fields_and_recent_files(self) -> None:
        context = compiler.compile_research_context(
            self.agent_root,
            {"project_id": self.project_a["id"], "user_message": "当前项目", "intent": "project_status"},
        )

        self.assertEqual(context["active_project_id"], self.project_a["id"])
        self.assertEqual(context["active_project_display_name"], "Alpha Macrophage")
        self.assertEqual(context["retrieval_scope"], "current_project")
        self.assertIn("recent_uploaded_files", context)
        self.assertIn("project_status_summary", context)
        self.assertIn("display_name", context["allowed_user_visible_identifiers"])
        self.assertIn("project_id", context["hidden_internal_identifiers"])

    def test_final_answer_sanitizer_hides_internal_ids_unless_developer_debug_is_enabled(self) -> None:
        raw = (
            f"project_id: {self.project_a['id']}\n"
            "candidate_id: cand_123\n"
            "task_id: task_123\n"
            "memory_id: mem_123\n"
            "file_id: file_123\n"
            "项目 Alpha Macrophage 已更新。"
        )

        safe = ros.final_answer_sanitizer(raw, message="保存结果")
        debug_request_without_mode = ros.final_answer_sanitizer(raw, message="显示调试信息和内部 ID")
        debug = ros.final_answer_sanitizer(raw, message="显示调试信息和内部 ID", developer_debug=True)

        for leaked in [self.project_a["id"], "cand_123", "task_123", "mem_123", "file_123"]:
            self.assertNotIn(leaked, safe)
            self.assertNotIn(leaked, debug_request_without_mode)
            self.assertIn(leaked, debug)
        self.assertIn("Alpha Macrophage", safe)

    def test_weekly_report_and_digest_default_to_current_project(self) -> None:
        report = ros.generate_report(
            self.agent_root,
            {"project_id": self.project_a["id"], "report_type": "weekly_report", "generate_claims": False},
        )
        digest = ros.generate_weekly_project_digest(
            self.agent_root,
            {"project_id": self.project_a["id"], "question": "alpha cytokine", "provider": "none"},
        )

        self.assertIn("alpha-file.csv", report["content_markdown"])
        self.assertNotIn("beta-file.csv", report["content_markdown"])
        self.assertEqual(digest["rag"]["retrieval_scope"], "current_project")
        self.assertTrue(all(item.get("project_id", self.project_a["id"]) == self.project_a["id"] for item in digest["rag"]["retrieved_chunks"]))


if __name__ == "__main__":
    unittest.main()
