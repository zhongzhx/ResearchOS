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


class ResearchOSResponsePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_response_policy_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(
            self.agent_root,
            {"title": "Response Policy Project", "research_area": "immune regulation macrophage"},
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def chat(self, message: str) -> dict:
        return ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": message})

    def create_indexed_papers(self, count: int = 5) -> None:
        task = ros.create_literature_search_task(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "query": "immune regulation macrophage NF-kB",
                "keywords": ["immune regulation", "macrophage", "NF-kB"],
                "provider": "all",
                "status": "running",
                "notes": ros.json_dumps({"phase": "second_pass"}),
            },
        )["task"]
        for index in range(1, count + 1):
            reference = ros.import_reference(
                self.agent_root,
                {
                    "project_id": self.project["id"],
                    "title": f"Macrophage NF-kB inflammatory regulation paper {index}",
                    "doi": f"10.5555/response-policy-{index}",
                    "year": str(2020 + index),
                    "journal": "Journal of Response Policy",
                    "authors": ["unknown_author"] if index == 1 else [f"Author {index}"],
                    "abstract": (
                        "RAW264.7 macrophages were stimulated with LPS to activate NF-kB signaling. "
                        "TNF-alpha and IL-6 were measured by ELISA, and NF-kB was assessed by Western blot. "
                        "The paper suggests NF-kB suppression reduces inflammatory cytokine production."
                    ),
                    "full_text": (
                        "Methods: RAW264.7 cells were treated with LPS. NF-kB pathway activity was measured by Western blot. "
                        "Cytokines including TNF-alpha and IL-6 were measured by ELISA."
                    ),
                    "source_provider": "test_fixture",
                    "search_task_id": task["id"],
                    "full_text_path": f"C:\\Users\\11710\\Desktop\\secret\\paper-{index}.pdf",
                    "access_status": "downloaded",
                    "evidence_level": "peer_reviewed_metadata",
                },
            )
            ros.build_project_research_kb(
                self.agent_root,
                {"project_id": self.project["id"], "reference_ids": [reference["id"]], "include_article_analysis": False},
            )
            ros.upsert_literature_ingest_item(
                self.agent_root,
                {
                    "task_id": task["id"],
                    "project_id": self.project["id"],
                    "record_id": f"response-record-{index}",
                    "reference_id": reference["id"],
                    "title": reference["title"],
                    "doi": reference["doi"],
                    "download_status": "downloaded",
                    "ingest_status": "indexed",
                    "chunks_count": len(reference.get("chunks") or []),
                },
            )

    def test_learning_summary_hides_paths_and_chunk_ids_by_default(self) -> None:
        self.create_indexed_papers(5)

        response = self.chat("你在文献搜索中学到了什么")

        self.assertEqual(response["response_mode"], "learning_summary")
        self.assertNotIn("C:\\", response["answer"])
        self.assertNotIn("/Users/", response["answer"])
        self.assertNotIn("chunk_id:", response["answer"])
        self.assertIn("Evidence strength", response["answer"])
        self.assertIn("Top relevant papers", response["answer"])

    def test_source_traceability_hides_internal_ids_by_default(self) -> None:
        self.create_indexed_papers(1)

        response = self.chat("你刚才总结来自哪些 chunk")

        self.assertEqual(response["response_mode"], "source_traceability")
        self.assertIn("citation id:", response["answer"])
        self.assertIn("short excerpt:", response["answer"])
        self.assertNotIn("chunk_id:", response["answer"])
        self.assertNotIn("reference_id:", response["answer"])
        self.assertNotIn("C:\\", response["answer"])

    def test_paper_recommendation_top_three_and_no_harvest(self) -> None:
        self.create_indexed_papers(5)

        response = self.chat("有什么高分文献值得读")

        self.assertEqual(response["intent"], "paper_recommendation")
        self.assertEqual(response["response_mode"], "paper_recommendation")
        self.assertIn("Top 3", response["answer"])
        self.assertLessEqual(response["answer"].count("\n"), 16)
        self.assertFalse(any(item.get("task_type") == "literature_harvest" and item.get("status") == "pending" for item in ros.latest_task_status(self.agent_root, self.project["id"])))

    def test_excluding_chat_and_literature_collection_is_capability_query(self) -> None:
        message = "\u9664\u4e86\u5bf9\u8bdd\u548c\u6536\u96c6\u6587\u732e\uff0c\u4f60\u8fd8\u80fd\u4e3a\u6211\u505a\u4ec0\u4e48"

        response = self.chat(message)

        self.assertEqual(ros.classify_research_intent(message), "capability_explanation")
        self.assertEqual(ros.infer_agent_intent(message), "capability_explanation")
        self.assertEqual(ros.extract_literature_keywords_from_message(message), [])
        self.assertEqual(response["intent"], "capability_explanation")
        self.assertEqual(response["response_mode"], "capability_explanation")
        self.assertIn("\u6587\u732e\u4e0e\u77e5\u8bc6\u5e93", response["answer"])
        self.assertIn("\u81ea\u4e3b\u5b66\u4e60\u4e0e\u5468\u62a5", response["answer"])
        self.assertIn("\u975e OA \u6587\u732e", response["answer"])
        self.assertIn("\u9879\u76ee\u8bb0\u5fc6\u4e0e artifact", response["answer"])
        self.assertNotIn("I can help with", response["answer"])
        self.assertNotIn("Start directly", response["answer"])
        self.assertFalse(any(item.get("task_type") == "literature_harvest" for item in ros.latest_task_status(self.agent_root, self.project["id"])))

    def test_followup_capability_answer_stays_chinese(self) -> None:
        message = "\u6211\u662f\u8bf4\u9664\u4e86\u8fd9\u4e24\u4e2a\u529f\u80fd\uff0c\u4f60\u8fd8\u6709\u4ec0\u4e48\u529f\u80fd\u53ef\u4ee5\u8f85\u52a9\u6211\u5de5\u4f5c"

        response = self.chat(message)

        self.assertEqual(response["intent"], "capability_explanation")
        self.assertIn("\u6587\u732e\u4e0e\u77e5\u8bc6\u5e93", response["answer"])
        self.assertIn("working", response["answer"])
        self.assertNotIn("qPCR", response["answer"])
        self.assertNotIn("96 \u5b54\u677f", response["answer"])
        self.assertNotIn("96-well", response["answer"])
        self.assertNotIn("I can help with", response["answer"])

    def test_skill_capability_question_uses_catalog(self) -> None:
        response = self.chat("\u4f60\u6709\u54ea\u4e9b skills")

        self.assertEqual(response["intent"], "capability_explanation")
        self.assertIn("capability_catalog", response)
        self.assertIn("working", response["answer"])
        self.assertIn("partial", response["answer"])
        self.assertNotIn("C:\\", response["answer"])
        self.assertNotIn("sk-", response["answer"].lower())

    def test_autonomous_learning_question_is_not_pure_task_status(self) -> None:
        message = "\u4f60\u4f1a\u81ea\u4e3b\u5b66\u4e60\u5417\uff1f\u4f8b\u5982\u627e\u975e OA \u6587\u732e\u8ba9\u6211\u4e0b\u8f7d"

        response = self.chat(message)

        self.assertEqual(ros.classify_research_intent(message), "autonomous_learning_question")
        self.assertEqual(ros.infer_agent_intent(message), "autonomous_learning_question")
        self.assertEqual(ros.extract_literature_keywords_from_message(message), [])
        self.assertEqual(response["intent"], "autonomous_learning_question")
        self.assertEqual(response["response_mode"], "autonomous_learning")
        self.assertIn("\u53d7\u63a7\u9879\u76ee\u7ea7\u5b66\u4e60", response["answer"])
        self.assertIn("\u4e0d\u4f1a\u8bad\u7ec3\u6a21\u578b\u6743\u91cd", response["answer"])
        self.assertIn("\u7528\u6237\u786e\u8ba4", response["answer"])
        self.assertNotEqual(response["response_mode"], "task_status")

    def test_unknown_author_and_internal_placeholders_are_hidden(self) -> None:
        self.create_indexed_papers(1)

        response = self.chat("你在文献搜索中学到了什么")

        self.assertNotIn("unknown_author", response["answer"])
        self.assertNotIn("null", response["answer"].lower())
        self.assertNotIn("nan", response["answer"].lower())

    def test_memory_commit_uses_result_template(self) -> None:
        task = ros.create_task(self.agent_root, {"project_id": self.project["id"], "task_type": "weekly_research_digest", "user_goal": "Weekly digest"})
        ros.run_research_workflow_task(self.agent_root, task["task_id"])

        response = self.chat("纳入项目记忆")

        self.assertEqual(response["response_mode"], "memory_commit_result")
        self.assertIn("memory_id:", response["answer"])
        self.assertIn("memory_type:", response["answer"])
        self.assertIn("source artifact:", response["answer"])
        self.assertIn("evidence_level:", response["answer"])

    def test_api_key_and_architecture_answers_are_stable_and_safe(self) -> None:
        api_response = self.chat("你的 API key 是什么")
        architecture = self.chat("你由多少个 agent 构成")

        self.assertNotIn("sk-", api_response["answer"].lower())
        self.assertIn("不会泄露 API key", api_response["answer"])
        self.assertEqual(architecture["response_mode"], "self_description")
        self.assertIn("不是模型权重自训练", architecture["answer"])
        self.assertIn("不保证永久保存所有 raw chat", architecture["answer"])

    def test_focus_keywords_ignore_generic_learning_and_recommendation_questions(self) -> None:
        for message in ["你学到了什么", "有什么高分文献值得读", "你怎么看", "给我讲讲", "生成周报", "纳入项目记忆"]:
            with self.subTest(message=message):
                self.assertEqual(ros.extract_literature_keywords_from_message(message), [])


if __name__ == "__main__":
    unittest.main()
