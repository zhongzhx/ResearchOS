import os
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


class AgentLiteratureChatFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_lit_chat_"))
        self.previous_harvest_limit = os.environ.get("RESEARCHOS_HARVEST_MAX_RESULTS_PER_QUERY")
        os.environ["RESEARCHOS_HARVEST_MAX_RESULTS_PER_QUERY"] = "1"
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(
            self.agent_root,
            {"title": "RAW264.7 immune project", "research_area": "immune regulation"},
        )
        self.original_run_agent_task = ros.run_agent_task

        def fake_run_agent_task(agent_root: Path, task_id: str, payload: dict) -> dict:
            task = ros.get_agent_task(agent_root, task_id)
            task_input = task.get("input") if isinstance(task.get("input"), dict) else {}
            lit_task = ros.create_literature_search_task(
                agent_root,
                {
                    **task_input,
                    "status": "running",
                    "references": [],
                    "notes": ros.json_dumps({"phase": "queued"}),
                },
            )["task"]
            updated = ros.update_agent_task(
                agent_root,
                task_id,
                {
                    "status": "running",
                    "progress": {"stage": "delegated", "literature_task_id": lit_task["id"]},
                    "artifacts": [{"type": "literature_search_task", "id": lit_task["id"]}],
                    "skip_memory_consolidation": True,
                },
            )
            return {"ok": True, "task": updated, "skill_run_id": "fake_skill_run"}

        ros.run_agent_task = fake_run_agent_task

    def tearDown(self) -> None:
        ros.run_agent_task = self.original_run_agent_task
        if self.previous_harvest_limit is None:
            os.environ.pop("RESEARCHOS_HARVEST_MAX_RESULTS_PER_QUERY", None)
        else:
            os.environ["RESEARCHOS_HARVEST_MAX_RESULTS_PER_QUERY"] = self.previous_harvest_limit
        shutil.rmtree(self.tmp, ignore_errors=True)

    def chat(self, message: str, conversation_id: str = "") -> dict:
        payload = {"project_id": self.project["id"], "message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        return ros.agent_chat(self.agent_root, payload)

    def create_indexed_literature_task(self, paper_count: int = 1) -> dict:
        task = ros.create_literature_search_task(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "query": "immune regulation RAW264.7 NF-kB",
                "keywords": ["immune regulation", "RAW264.7", "NF-kB"],
                "provider": "all",
                "status": "running",
                "references": [],
                "notes": ros.json_dumps({"phase": "second_pass"}),
            },
        )["task"]
        references = []
        for index in range(1, paper_count + 1):
            reference = ros.import_reference(
                self.agent_root,
                {
                    "project_id": self.project["id"],
                    "title": f"NF-kB regulation in RAW264.7 macrophage inflammatory activation {index}",
                    "doi": f"10.1234/raw-nfkb-{index}",
                    "year": str(2020 + index),
                    "journal": "Journal of Macrophage Models",
                    "authors": [f"Author {index}"],
                    "abstract": (
                        "RAW264.7 macrophages were stimulated with LPS to activate NF-kB signaling. "
                        "The study measured TNF-alpha and IL-6 by ELISA and used Western blot to assess pathway activation. "
                        f"The indexed paper {index} suggests that suppressing NF-kB reduces inflammatory cytokine production in this macrophage model."
                    ),
                    "source_provider": "test_fixture",
                    "search_task_id": task["id"],
                    "full_text": (
                        "Methods: RAW264.7 cells were treated with LPS. NF-kB pathway activity was measured by Western blot. "
                        "Cytokines including TNF-alpha and IL-6 were measured by ELISA."
                    ),
                    "access_status": "downloaded",
                    "evidence_level": "peer_reviewed_metadata",
                },
            )
            references.append(reference)
            ros.build_project_research_kb(
                self.agent_root,
                {"project_id": self.project["id"], "reference_ids": [reference["id"]], "include_article_analysis": False},
            )
            ros.upsert_literature_ingest_item(
                self.agent_root,
                {
                    "task_id": task["id"],
                    "project_id": self.project["id"],
                    "record_id": f"record-{index}",
                    "reference_id": reference["id"],
                    "title": reference["title"],
                    "doi": reference["doi"],
                    "download_status": "downloaded",
                    "ingest_status": "indexed",
                    "chunks_count": len(reference.get("chunks") or []),
                },
            )
        task["references"] = references
        return task

    def test_keyword_parser_preserves_english_first_character_and_mixed_separators(self) -> None:
        keywords = ros.extract_literature_keywords_from_message(
            "I want to search immune regulation、RAW264.7、NF-κB three keywords"
        )

        self.assertEqual(keywords, ["immune regulation", "RAW264.7", "NF-κB"])

    def test_chat_flow_prepares_then_directly_starts_literature_harvest(self) -> None:
        project_answer = self.chat("What project are we working on?")
        self.assertTrue(project_answer["ok"])
        self.assertEqual(project_answer["workspace_state"]["project"]["title"], "RAW264.7 immune project")

        skills_answer = self.chat("What skills do you have?", project_answer["conversation_id"])
        self.assertTrue(skills_answer["ok"])
        self.assertIn("文献采集", skills_answer["answer"])
        self.assertNotIn("core_keyword_research_harvest", skills_answer["answer"])

        prepare = self.chat("I want to search immune regulation, RAW264.7, NF-κB", project_answer["conversation_id"])
        self.assertTrue(prepare["ok"])
        self.assertEqual(prepare["intent"], "literature_harvest_prepare")
        self.assertEqual(prepare["literature_keywords"], ["immune regulation", "RAW264.7", "NF-κB"])

        started = self.chat("Start directly", project_answer["conversation_id"])
        self.assertTrue(started["ok"])
        self.assertEqual(started["intent"], "start_skill_request")
        self.assertIn("task", started)
        self.assertEqual(started["task"]["status"], "running")
        self.assertEqual(started["task"]["current_stage"], "searching")
        self.assertEqual(started["task"]["counters"], {"found": 0, "downloaded": 0, "parsed": 0, "ingested": 0, "failed": 0})
        self.assertEqual(started["task"]["keywords"], ["immune regulation", "RAW264.7", "NF-κB"])
        self.assertNotIn("manual", started["answer"].lower())
        self.assertNotIn("mock", started["answer"].lower())
        self.assertNotIn("browser", started["answer"].lower())

        status = self.chat("Has it started?", project_answer["conversation_id"])
        self.assertTrue(status["ok"])
        self.assertEqual(status["intent"], "task_status_query")
        self.assertIn("current_stage", status["answer"])
        self.assertTrue(status["task_status"])
        lit_status = next(item for item in status["task_status"] if item["task_type"] == "literature_harvest")
        self.assertEqual(lit_status["current_stage"], "searching")
        self.assertEqual(lit_status["counters"], {"found": 0, "downloaded": 0, "parsed": 0, "ingested": 0, "failed": 0})

    def test_learning_question_returns_ingested_paper_summary_not_only_counters(self) -> None:
        self.create_indexed_literature_task()

        response = self.chat("Have you learned anything?")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "literature_learning_summary")
        self.assertIn("LiteratureLearningSummarySkill", [call.get("tool") for call in response["tool_calls"]])
        self.assertEqual(response["learning_summary"]["ingested_paper_count"], 1)
        self.assertIn("Only 1 paper has been ingested", response["answer"])
        self.assertIn("NF-kB regulation in RAW264.7", response["answer"])
        self.assertNotIn("Counters: found", response["answer"])

    def test_parsed_paper_question_uses_learning_summary_skill(self) -> None:
        self.create_indexed_literature_task()

        response = self.chat("Tell me what you learned from the parsed paper.")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "literature_learning_summary")
        self.assertIn("LiteratureLearningSummarySkill", [call.get("tool") for call in response["tool_calls"]])
        self.assertIn("RAW264.7", response["answer"])

    def test_started_question_still_returns_task_status(self) -> None:
        self.create_indexed_literature_task()

        response = self.chat("Has it started?")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "task_status_query")
        self.assertIn("Counters:", response["answer"])

    def test_current_harvest_status_still_returns_task_status(self) -> None:
        self.create_indexed_literature_task()

        response = self.chat("What is the current harvest status?")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "task_status_query")
        self.assertIn("Status:", response["answer"])

    def test_real_chat_path_preserves_immune_regulation_keyword(self) -> None:
        response = self.chat("I want to search immune regulation, RAW264.7, NF-kB")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "literature_harvest_prepare")
        self.assertEqual(response["literature_keywords"][0], "immune regulation")
        self.assertNotEqual(response["literature_keywords"][0], "mmune regulation")

    def test_stale_combined_malformed_keyword_is_display_corrected(self) -> None:
        task = ros.create_literature_search_task(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "query": "mmune regulation、RAW264.7、NF-kB",
                "keywords": ["mmune regulation、RAW264.7、NF-kB"],
                "provider": "all",
                "status": "running",
                "references": [],
            },
        )["task"]

        status = ros.latest_task_status(self.agent_root, self.project["id"], limit=3)
        lit = next(item for item in status if item["task_id"] == task["id"])

        self.assertEqual(lit["keywords"], ["immune regulation", "RAW264.7", "NF-kB"])
        self.assertEqual(lit["query"], "immune regulation、RAW264.7、NF-kB")


    def test_ingested_inventory_question_lists_papers_not_task_status(self) -> None:
        self.create_indexed_literature_task(paper_count=3)

        response = self.chat("当前已入库文献有哪些？按 title、year、doi、chunk count 列出来。")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "ingested_paper_inventory")
        self.assertIn("ListIngestedPapersSkill", [call.get("tool") for call in response["tool_calls"]])
        self.assertEqual(response["ingested_paper_inventory"]["ingested_paper_count"], 3)
        self.assertIn("NF-kB regulation in RAW264.7 macrophage inflammatory activation 1", response["answer"])
        self.assertIn("chunk_count", response["answer"])
        self.assertNotIn("Counters:", response["answer"])

    def test_started_question_still_returns_task_status_with_inventory_route_present(self) -> None:
        self.create_indexed_literature_task(paper_count=3)

        response = self.chat("Has it started?")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "task_status_query")
        self.assertIn("Counters:", response["answer"])

    def test_chinese_parsed_ingested_inventory_returns_metadata_and_chunk_count(self) -> None:
        self.create_indexed_literature_task(paper_count=1)

        response = self.chat("列出已经解析入库的文献")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "ingested_paper_inventory")
        paper = response["ingested_paper_inventory"]["papers"][0]
        self.assertEqual(paper["title"], "NF-kB regulation in RAW264.7 macrophage inflammatory activation 1")
        self.assertEqual(paper["doi"], "10.1234/raw-nfkb-1")
        self.assertEqual(paper["year"], "2021")
        self.assertGreater(paper["chunk_count"], 0)
        self.assertIn("10.1234/raw-nfkb-1", response["answer"])

    def test_inventory_question_with_zero_ingested_papers_returns_empty_message(self) -> None:
        response = self.chat("show ingested papers")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "ingested_paper_inventory")
        self.assertEqual(response["ingested_paper_inventory"]["ingested_paper_count"], 0)
        self.assertIn("No papers have been ingested into the knowledge base yet.", response["answer"])

    def test_inventory_with_three_ingested_papers_returns_three_not_only_counters(self) -> None:
        self.create_indexed_literature_task(paper_count=3)

        response = self.chat("当前 3 篇入库文献分别是什么？按 title、year、doi、ingested chunk count、one sentence summary 列出来。")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "ingested_paper_inventory")
        self.assertEqual(len(response["ingested_paper_inventory"]["papers"]), 3)
        self.assertIn("Current KB inventory shows 3 indexed papers", response["answer"])
        self.assertIn("one_sentence_summary", response["answer"])
        self.assertNotIn("found 0, downloaded 0", response["answer"])


    def test_learning_summary_contains_chunk_ids_used(self) -> None:
        task = self.create_indexed_literature_task()

        summary = ros.literature_learning_summary_skill(
            self.agent_root,
            {"project_id": self.project["id"], "task_id": task["id"], "max_papers": 1},
        )

        paper = summary["papers"][0]
        chunk_ids = [chunk["id"] for chunk in task["references"][0]["chunks"]]
        self.assertTrue(paper["chunk_ids_used"])
        self.assertEqual(paper["chunk_ids_used"], chunk_ids[: len(paper["chunk_ids_used"])])
        self.assertEqual(paper["chunk_ids"], paper["chunk_ids_used"])

    def test_learning_summary_key_points_have_source_anchors(self) -> None:
        task = self.create_indexed_literature_task()

        summary = ros.literature_learning_summary_skill(
            self.agent_root,
            {"project_id": self.project["id"], "task_id": task["id"], "max_papers": 1},
        )

        key_points = summary["papers"][0]["key_points"]
        supported = [point for point in key_points if point["evidence_level"] == "supported_by_source"]
        self.assertTrue(supported)
        self.assertTrue(supported[0]["source_anchors"][0]["chunk_id"])
        self.assertEqual(supported[0]["source_anchors"][0]["reference_id"], task["references"][0]["id"])

    def test_formatter_preserves_source_anchors_for_traceability(self) -> None:
        task = self.create_indexed_literature_task()
        summary = ros.literature_learning_summary_skill(
            self.agent_root,
            {"project_id": self.project["id"], "task_id": task["id"], "max_papers": 1},
        )

        answer = ros.format_literature_source_traceability(summary, include_internal_ids=True)

        chunk_id = summary["papers"][0]["chunk_ids_used"][0]
        self.assertIn("chunk_id:", answer)
        self.assertIn(chunk_id, answer)
        self.assertIn(summary["papers"][0]["reference_id"], answer)
        self.assertIn("short excerpt:", answer)

    def test_chunk_trace_followup_returns_real_chunk_ids(self) -> None:
        self.create_indexed_literature_task()
        first = self.chat("Have you learned anything?")

        response = self.chat(
            "\u8fd9\u7bc7\u300aNF-kB\u300b(2021) \u7684 DOI\u3001\u671f\u520a\u3001\u4f5c\u8005\u548c reference_id \u662f\u4ec0\u4e48\uff1f"
            "\u4f60\u521a\u624d\u603b\u7ed3\u7684\u5185\u5bb9\u5206\u522b\u6765\u81ea\u54ea\u4e9b chunk\uff1f",
            first["conversation_id"],
        )

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "literature_source_traceability")
        self.assertIn("LiteratureSourceTraceabilitySkill", [call.get("tool") for call in response["tool_calls"]])
        self.assertIn("citation id:", response["answer"])
        self.assertIn("short excerpt:", response["answer"])
        self.assertNotIn("chunk_id:", response["answer"])
        self.assertNotIn("reference_id:", response["answer"])
        self.assertNotIn("cannot precisely identify chunk_id", response["answer"])

    def test_missing_chunks_reports_metadata_missing(self) -> None:
        task = self.create_indexed_literature_task()
        reference_id = task["references"][0]["id"]
        conn = ros.connect(self.agent_root)
        try:
            conn.execute("DELETE FROM knowledge_base_entries WHERE project_id=? AND source_reference_id=?", (self.project["id"], reference_id))
            conn.execute("DELETE FROM reference_chunks WHERE project_id=? AND reference_id=?", (self.project["id"], reference_id))
            conn.commit()
        finally:
            conn.close()

        summary = ros.literature_learning_summary_skill(
            self.agent_root,
            {"project_id": self.project["id"], "task_id": task["id"], "max_papers": 1},
        )
        answer = ros.format_literature_source_traceability(summary)

        self.assertIn("The current KB records do not contain public source excerpts for this source.", answer)
        self.assertNotIn("chunk_id: ref_", answer)

    def test_unsupported_claim_marked_without_anchors(self) -> None:
        key_points = ros.build_source_anchored_key_points(["Unsupported generated claim"], [])

        self.assertEqual(key_points[0]["evidence_level"], "unsupported_by_retrieved_chunks")
        self.assertEqual(key_points[0]["source_anchors"], [])

    def test_unknown_author_is_not_shown_in_inventory_or_learning(self) -> None:
        self.create_indexed_literature_task()
        conn = ros.connect(self.agent_root)
        try:
            conn.execute('UPDATE "references" SET authors_json=? WHERE project_id=?', (ros.json_dumps(["unknown_author"]), self.project["id"]))
            conn.commit()
        finally:
            conn.close()

        inventory = self.chat("show ingested papers")
        learning = self.chat("Have you learned anything?")

        self.assertNotIn("unknown_author", inventory["answer"])
        self.assertNotIn("unknown_author", learning["answer"])
        self.assertIn("authors not available in local metadata", inventory["answer"])
        self.assertIn("authors not available in local metadata", learning["answer"])

    def test_missing_metadata_uses_user_facing_fallbacks(self) -> None:
        self.create_indexed_literature_task()
        conn = ros.connect(self.agent_root)
        try:
            conn.execute('UPDATE "references" SET year="", doi="", journal="", full_text_path="", source_path="", authors_json=? WHERE project_id=?', (ros.json_dumps([]), self.project["id"]))
            conn.commit()
        finally:
            conn.close()

        response = self.chat("show ingested papers")

        self.assertIn("year not available", response["answer"])
        self.assertIn("DOI not available", response["answer"])
        self.assertIn("journal not available", response["answer"])
        self.assertIn("authors not available in local metadata", response["answer"])
        self.assertIn("source file not available", response["answer"])
        for raw in ["unknown_author", "none", "null", "nan"]:
            self.assertNotIn(raw, response["answer"].lower())

    def test_inventory_template_includes_project_name_and_metadata_fields(self) -> None:
        self.create_indexed_literature_task(paper_count=2)

        response = self.chat("What papers have been indexed?")

        self.assertEqual(response["intent"], "ingested_paper_inventory")
        self.assertIn("Current KB inventory shows 2 indexed papers for project RAW264.7 immune project", response["answer"])
        for label in ["title:", "year:", "DOI:", "journal:", "authors:", "chunk_count:", "one_sentence_summary:"]:
            self.assertIn(label, response["answer"])
        self.assertNotIn("reference_id:", response["answer"])
        self.assertNotIn("Current harvest task status", response["answer"])

    def test_learning_template_not_task_status_and_mentions_source_based_summary(self) -> None:
        self.create_indexed_literature_task(paper_count=2)

        response = self.chat("What did you learn from the ingested papers?")

        self.assertEqual(response["intent"], "literature_learning_summary")
        self.assertIn("source-based summary", response["answer"])
        self.assertIn("Evidence strength:", response["answer"])
        self.assertIn("Source anchors:", response["answer"])
        self.assertNotIn("Current harvest task status", response["answer"])

    def test_source_traceability_template_has_claim_and_source_fields(self) -> None:
        self.create_indexed_literature_task()

        response = self.chat("What chunks support this?")

        self.assertEqual(response["intent"], "literature_source_traceability")
        self.assertIn("Here are the source chunks supporting the previous summary.", response["answer"])
        self.assertIn("claim:", response["answer"])
        self.assertIn("citation id:", response["answer"])
        self.assertIn("short excerpt:", response["answer"])
        self.assertNotIn("chunk_id:", response["answer"])
        self.assertIn("DOI:", response["answer"])
        self.assertIn("source file:", response["answer"])

    def test_chinese_singular_chunk_source_question_routes_to_traceability(self) -> None:
        self.create_indexed_literature_task()

        response = self.chat("\u521a\u624d\u4f60\u8bf4 NF-\u03baB \u8c03\u63a7 TNF-\u03b1\u3001IL-6\uff0c\u8fd9\u53e5\u8bdd\u6765\u81ea\u54ea\u4e2a chunk\uff1f")

        self.assertEqual(response["intent"], "literature_source_traceability")
        self.assertIn("citation id:", response["answer"])
        self.assertIn("short excerpt:", response["answer"])
        self.assertNotIn("chunk_id:", response["answer"])

    def test_status_template_still_returns_task_status(self) -> None:
        self.create_indexed_literature_task()

        response = self.chat("What is the current harvest status?")

        self.assertEqual(response["intent"], "task_status_query")
        self.assertIn("Current harvest task status:", response["answer"])
        self.assertIn("current_stage:", response["answer"])
        self.assertNotIn("task_id:", response["answer"])

    def test_dynamic_count_wording_present_when_harvest_running(self) -> None:
        self.create_indexed_literature_task(paper_count=5)

        response = self.chat("show ingested papers")

        self.assertIn("The harvest may still be running, so this number can continue to change.", response["answer"])

    def test_backfill_reference_metadata_noop_hook_skips_without_provider(self) -> None:
        task = self.create_indexed_literature_task()

        result = ros.backfill_reference_metadata(self.agent_root, task["references"][0]["id"])

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
