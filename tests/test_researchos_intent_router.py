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


class ResearchOSIntentRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aura_intent_"))
        self.agent_root = self.temp_dir / "agent_data"
        self.project = ros.create_project(
            self.agent_root,
            {"title": "Intent Router Project", "research_area": "immune regulation"},
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_classifier_distinguishes_required_research_intents(self) -> None:
        cases = {
            "有什么高分文献值得读？": "paper_recommendation",
            "帮我搜索 NF-κB macrophage inflammation 文献": "literature_harvest_start",
            "现在采集到哪了？": "task_status",
            "你学到了什么？": "proactive_status_query",
            "把刚才周报保存": "memory_commit_request",
            "我刚才第一句话是什么？": "raw_conversation_recall",
            "你的记忆架构是什么？": "self_description_or_architecture",
            "我是新手，给我科普一下这个方向": "general_scientific_explanation",
        }

        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(ros.classify_research_intent(message), expected)

    def test_recommendation_question_does_not_prepare_or_start_harvest(self) -> None:
        response = ros.agent_chat(
            self.agent_root,
            {"project_id": self.project["id"], "message": "有什么高分文献值得读？"},
        )

        self.assertEqual(response["intent"], "paper_recommendation")
        self.assertNotEqual(response["intent"], "literature_harvest_prepare")
        self.assertFalse(response.get("literature_keywords"))
        self.assertFalse(ros.latest_task_status(self.agent_root, self.project["id"]))

    def test_beginner_explanation_is_not_saved_as_user_profile(self) -> None:
        response = ros.agent_chat(
            self.agent_root,
            {"project_id": self.project["id"], "message": "我是新手，给我科普一下这个方向"},
        )

        self.assertEqual(response["intent"], "general_scientific_explanation")
        self.assertNotIn(response["intent"], ros.PROFILE_UPDATE_INTENTS)
        self.assertEqual(ros.workspace_state(self.agent_root, self.project["id"])["memory"]["agent_memory_count"], 0)

    def test_legacy_chat_routes_still_use_existing_task_status_and_start_paths(self) -> None:
        self.assertEqual(ros.infer_agent_intent("帮我搜索 NF-κB macrophage inflammation 文献"), "start_skill_request")
        self.assertEqual(ros.infer_agent_intent("现在采集到哪了？"), "task_status_query")

    def test_status_query_phrases_route_to_status_intents(self) -> None:
        cases = {
            "最近有什么进展": ("proactive_status_query", "proactive_status_query"),
            "现在跑到哪了": ("task_status", "task_status_query"),
            "文献采集完成了吗": ("task_status", "task_status_query"),
            "你学到了什么": ("proactive_status_query", "proactive_status_query"),
            "what is the current progress": ("task_status", "task_status_query"),
            "any updates on this project": ("proactive_status_query", "proactive_status_query"),
        }

        for message, (classifier_intent, agent_intent) in cases.items():
            with self.subTest(message=message):
                self.assertEqual(ros.classify_research_intent(message), classifier_intent)
                self.assertEqual(ros.infer_agent_intent(message), agent_intent)
                self.assertNotEqual(ros.infer_agent_intent(message), "general_scientific_explanation")

    def test_latest_chat_intent_ignores_assistant_metadata_intent(self) -> None:
        session = ros.ensure_chat_session(self.agent_root, self.project["id"], "assistant-intent-history", title="History")
        ros.save_chat_message(
            self.agent_root,
            session["id"],
            "user",
            "explain NF-kB signaling",
            {"project_id": self.project["id"]},
            project_id=self.project["id"],
        )
        ros.save_chat_message(
            self.agent_root,
            session["id"],
            "assistant",
            "Here is a status-shaped answer.",
            {"project_id": self.project["id"], "intent": "task_status_query"},
            project_id=self.project["id"],
        )

        history = ros.list_chat_messages(self.agent_root, session["id"], self.project["id"], limit=10)
        assistant_metadata = history[-1]["metadata"]

        self.assertEqual(ros.latest_chat_intent(history), "")
        self.assertNotIn("intent", assistant_metadata)
        self.assertEqual(assistant_metadata.get("assistant_response_type"), "task_status_query")

    def test_research_advice_history_does_not_block_next_status_query(self) -> None:
        session = ros.ensure_chat_session(self.agent_root, self.project["id"], "research-then-status", title="History")
        ros.save_chat_message(
            self.agent_root,
            session["id"],
            "user",
            "explain macrophage NF-kB signaling",
            {"project_id": self.project["id"], "intent": "research_advice"},
            project_id=self.project["id"],
        )

        response = ros.agent_chat(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "conversation_id": session["id"],
                "message": "\u6700\u8fd1\u6709\u4ec0\u4e48\u8fdb\u5c55",
            },
        )

        self.assertEqual(response["intent"], "proactive_status_query")
        self.assertEqual(response["response_mode"], "task_status")

    def test_task_status_history_does_not_force_next_science_question_to_status(self) -> None:
        session = ros.ensure_chat_session(self.agent_root, self.project["id"], "status-then-science", title="History")
        ros.save_chat_message(
            self.agent_root,
            session["id"],
            "user",
            "what is the current progress",
            {"project_id": self.project["id"], "intent": "task_status_query"},
            project_id=self.project["id"],
        )
        ros.save_chat_message(
            self.agent_root,
            session["id"],
            "assistant",
            "No active task is running.",
            {"project_id": self.project["id"], "intent": "task_status_query"},
            project_id=self.project["id"],
        )

        response = ros.agent_chat(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "conversation_id": session["id"],
                "message": "explain NF-kB signaling in macrophage inflammation",
            },
        )

        self.assertEqual(response["intent"], "general_scientific_explanation")
        self.assertNotEqual(response["response_mode"], "task_status")

    def test_status_query_context_reads_project_tasks_runs_memory_files_and_summary(self) -> None:
        ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "filename": "status-source.pdf",
                "content": "status source",
                "file_type": "pdf",
            },
        )
        run = ros.start_service_skill_run(
            self.agent_root,
            "unit_status_skill",
            "UnitStatusSkill",
            self.project["id"],
            {"project_id": self.project["id"]},
        )
        ros.finish_service_skill_run(
            self.agent_root,
            run["id"],
            {"project_id": self.project["id"], "result": "ok"},
            [{"type": "report", "id": "status-report"}],
            ["status run completed"],
        )

        for intent in ["task_status_query", "project_status_query", "proactive_status_query"]:
            with self.subTest(intent=intent):
                context = compiler.compile_research_context(
                    self.agent_root,
                    {"project_id": self.project["id"], "user_message": "status", "intent": intent},
                )

                self.assertEqual(context["active_project_display_name"], "Intent Router Project")
                self.assertTrue(context["recent_uploaded_files"])
                self.assertGreaterEqual(context["project_status_summary"]["file_count"], 1)
                self.assertGreaterEqual(context["project_status_summary"]["tasks_count"], 1)
                self.assertTrue(any(item["task_type"] == "skill_run" for item in context["task_status"]))
                self.assertTrue(any(item["task_type"] == "execution_memory" for item in context["task_status"]))
                context_types = {item["source_type"] for item in context["context_items"]}
                self.assertIn("project", context_types)
                self.assertIn("task_status", context_types)

    def test_status_message_forces_task_context_even_when_intent_is_misclassified(self) -> None:
        ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "filename": "status-source.pdf",
                "content": "status source",
                "file_type": "pdf",
            },
        )
        ros.create_agent_memory_entry(
            self.agent_root,
            {
                "memory_scope": "project",
                "project_id": self.project["id"],
                "memory_type": "project_note",
                "title": "Memory should not outrank status",
                "content": "Long-term memory is useful but should not be the primary context for progress queries.",
            },
        )
        reference = ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "RAG should be supplemental",
                "abstract": "Evidence exists but should not outrank current task status.",
                "full_text": "Evidence exists but should not outrank current task status.",
                "source_provider": "unit",
            },
        )
        ros.build_project_research_kb(
            self.agent_root,
            {"project_id": self.project["id"], "reference_ids": [reference["id"]], "include_article_analysis": False},
        )
        run = ros.start_service_skill_run(
            self.agent_root,
            "unit_status_skill",
            "UnitStatusSkill",
            self.project["id"],
            {"project_id": self.project["id"]},
        )
        ros.finish_service_skill_run(
            self.agent_root,
            run["id"],
            {"project_id": self.project["id"], "result": "ok"},
            [{"type": "report", "id": "status-report"}],
            ["status run completed"],
        )

        context = compiler.compile_research_context(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "user_message": "最近有什么进展",
                "intent": "general_scientific_explanation",
            },
        )

        self.assertTrue(context["recent_uploaded_files"])
        self.assertGreaterEqual(context["project_status_summary"]["tasks_count"], 1)
        self.assertTrue(any(item["task_type"] == "skill_run" for item in context["task_status"]))
        self.assertTrue(any(item["task_type"] == "execution_memory" for item in context["task_status"]))
        compiled = context["compiled_context"]
        for heading in [
            "Project summary",
            "Current task status",
            "Recent uploaded files",
            "Relevant memory",
            "Evidence/RAG",
        ]:
            self.assertIn(heading, compiled)
        self.assertLess(compiled.index("Current task status"), compiled.index("Relevant memory"))
        self.assertLess(compiled.index("Current task status"), compiled.index("Evidence/RAG"))
        context_types = [item["source_type"] for item in context["context_items"][:3]]
        self.assertIn("task_status", context_types)
        self.assertNotEqual(context["context_items"][0]["source_type"], "rag_chunk")

    def test_task_status_answer_does_not_expose_internal_ids(self) -> None:
        run = ros.start_service_skill_run(
            self.agent_root,
            "unit_status_skill",
            "UnitStatusSkill",
            self.project["id"],
            {"project_id": self.project["id"]},
        )
        ros.finish_service_skill_run(
            self.agent_root,
            run["id"],
            {"project_id": self.project["id"], "result": "ok"},
            [{"type": "report", "id": "status-report"}],
            ["status run completed"],
        )

        response = ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": "现在跑到哪了"})

        self.assertEqual(response["intent"], "task_status_query")
        self.assertNotIn("task_id", response["answer"])
        self.assertNotIn("memory_id", response["answer"])
        self.assertNotIn("candidate_id", response["answer"])
        self.assertNotIn("project_id", response["answer"])
        self.assertNotIn(run["id"], response["answer"])

    def test_capability_and_autonomous_learning_intents_precede_harvest(self) -> None:
        cases = {
            "\u9664\u4e86\u5bf9\u8bdd\u548c\u6536\u96c6\u6587\u732e\uff0c\u4f60\u8fd8\u80fd\u4e3a\u6211\u505a\u4ec0\u4e48": "capability_explanation",
            "\u4f60\u6709\u4ec0\u4e48\u529f\u80fd\u53ef\u4ee5\u8f85\u52a9\u6211\u5de5\u4f5c": "capability_explanation",
            "\u4f60\u6709\u54ea\u4e9b skills": "capability_explanation",
            "what capabilities do you have": "capability_explanation",
            "\u4f60\u4f1a\u81ea\u4e3b\u5b66\u4e60\u5417\uff1f\u4f8b\u5982\u627e\u975e OA \u6587\u732e\u8ba9\u6211\u4e0b\u8f7d": "autonomous_learning_question",
            "\u73b0\u5728\u91c7\u96c6\u5230\u54ea\u4e86": "task_status",
            "\u5e2e\u6211\u91c7\u96c6 NF-\u03baB \u6587\u732e": "literature_harvest_start",
        }

        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(ros.classify_research_intent(message), expected)

    def test_capability_catalog_exposes_normalized_statuses(self) -> None:
        catalog = ros.build_capability_catalog(self.agent_root, self.project["id"])
        statuses = {item["status"] for item in catalog["items"]}

        self.assertTrue({"working", "partial", "mock", "missing"}.issubset(statuses))
        self.assertIn("skill_registry", catalog["sources"])
        self.assertIn("workflow_registry", catalog["sources"])
        self.assertIn("literature_tools", catalog["sources"])


if __name__ == "__main__":
    unittest.main()
