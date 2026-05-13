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


class ResearchOSNonOAPaperRequestFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_non_oa_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(
            self.agent_root,
            {
                "title": "Non-OA Literature Project",
                "research_area": "NF-kB macrophage inflammation",
                "keywords": ["NF-kB", "macrophage", "inflammation"],
            },
        )
        self.task = ros.create_literature_search_task(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "query": "NF-kB macrophage inflammation",
                "keywords": ["NF-kB", "macrophage", "inflammation"],
                "provider": "all",
                "status": "running",
                "references": [],
                "notes": ros.json_dumps({"phase": "running"}),
            },
        )["task"]

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_non_oa_reference(self) -> dict:
        return ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "NF-kB macrophage inflammation mechanism",
                "authors": ["Lee A", "Chen B"],
                "year": "2021",
                "journal": "Journal of Inflammation Research",
                "doi": "10.1234/nonoa.2021.001",
                "url": "https://example.org/non-oa-paper",
                "abstract": "NF-kB regulates macrophage inflammatory cytokines including TNF-alpha and IL-6.",
                "source_type": "keyword_harvest_reference",
                "source_provider": "test",
                "search_task_id": self.task["id"],
                "access_status": "download_failed",
                "relevance_score": 0.95,
                "reason_for_inclusion": "High overlap with NF-kB macrophage inflammation project keywords.",
            },
        )

    def test_failed_high_value_reference_generates_paper_request(self) -> None:
        reference = self.make_non_oa_reference()

        result = ros.generate_paper_requests_for_task(
            self.agent_root,
            {"project_id": self.project["id"], "task_id": self.task["id"]},
        )

        self.assertEqual(result["created_count"], 1)
        requests = ros.list_paper_requests(self.agent_root, project_id=self.project["id"])
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["reference_id"], reference["id"])
        self.assertEqual(requests[0]["access_status"], "download_failed")
        self.assertEqual(requests[0]["status"], "pending")
        self.assertIn("NF-kB", requests[0]["suggested_filename"])

    def test_chat_lists_papers_that_need_user_download(self) -> None:
        self.make_non_oa_reference()
        ros.generate_paper_requests_for_task(
            self.agent_root,
            {"project_id": self.project["id"], "task_id": self.task["id"]},
        )

        response = ros.agent_chat(
            self.agent_root,
            {"project_id": self.project["id"], "message": "有哪些文献需要我下载？"},
        )

        self.assertEqual(response["intent"], "paper_request_list")
        self.assertIn("需要你下载", response["answer"])
        self.assertIn("NF-kB macrophage inflammation mechanism", response["answer"])
        self.assertIn("10.1234/nonoa.2021.001", response["answer"])
        self.assertIn("watch folder", response["answer"].lower())

    def test_user_pdf_in_watch_folder_matches_request_and_ingests(self) -> None:
        self.make_non_oa_reference()
        ros.generate_paper_requests_for_task(
            self.agent_root,
            {"project_id": self.project["id"], "task_id": self.task["id"]},
        )
        watch_folder = ros.paper_request_watch_folder(self.agent_root, self.project["id"])
        pdf_path = watch_folder / "NF-kB_macrophage_inflammation_mechanism_10.1234_nonoa.2021.001.pdf"
        pdf_path.write_text(
            (
                "NF-kB macrophage inflammation mechanism. "
                "RAW264.7 macrophages were stimulated with LPS. "
                "NF-kB inhibition reduced TNF-alpha and IL-6 expression."
            ),
            encoding="utf-8",
        )

        result = ros.process_user_downloaded_pdfs(
            self.agent_root,
            {"project_id": self.project["id"], "task_id": self.task["id"]},
        )

        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["ingested_count"], 1)
        request = ros.list_paper_requests(self.agent_root, project_id=self.project["id"])[0]
        self.assertEqual(request["status"], "ingested")
        chunks = ros.list_reference_chunks(self.agent_root, project_id=self.project["id"], reference_id=request["reference_id"])
        self.assertGreaterEqual(len(chunks), 1)
        kb_entries = ros.list_knowledge_base_entries(self.agent_root, project_id=self.project["id"])
        self.assertTrue(any(entry["source_reference_id"] == request["reference_id"] for entry in kb_entries))
        status = next(item for item in ros.latest_task_status(self.agent_root, self.project["id"], limit=5) if item.get("task_type") == "literature_harvest")
        self.assertEqual(status["counters"]["user_uploaded_ingested_count"], 1)

    def test_chat_processes_user_downloaded_pdf_followup(self) -> None:
        self.make_non_oa_reference()
        ros.generate_paper_requests_for_task(
            self.agent_root,
            {"project_id": self.project["id"], "task_id": self.task["id"]},
        )
        watch_folder = ros.paper_request_watch_folder(self.agent_root, self.project["id"])
        (watch_folder / "10.1234_nonoa.2021.001.pdf").write_text(
            "NF-kB macrophage inflammation mechanism. NF-kB inhibition reduced TNF-alpha and IL-6 expression.",
            encoding="utf-8",
        )

        response = ros.agent_chat(
            self.agent_root,
            {"project_id": self.project["id"], "message": "我已经把 PDF 放进文件夹了，继续处理我补充的 PDF"},
        )

        self.assertEqual(response["intent"], "paper_request_process")
        self.assertIn("ingested: 1", response["answer"])
        request = ros.list_paper_requests(self.agent_root, project_id=self.project["id"])[0]
        self.assertEqual(request["status"], "ingested")

    def test_unmatched_pdf_enters_unmatched_queue_with_reason(self) -> None:
        watch_folder = ros.paper_request_watch_folder(self.agent_root, self.project["id"])
        pdf_path = watch_folder / "unrelated_uploaded_paper.pdf"
        pdf_path.write_text("This PDF does not match any pending paper request.", encoding="utf-8")

        result = ros.process_user_downloaded_pdfs(
            self.agent_root,
            {"project_id": self.project["id"], "task_id": self.task["id"]},
        )

        self.assertEqual(result["matched_count"], 0)
        self.assertEqual(result["unmatched_count"], 1)
        unmatched = ros.list_unmatched_pdfs(self.agent_root, project_id=self.project["id"])
        self.assertEqual(len(unmatched), 1)
        self.assertIn("No pending paper_request matched", unmatched[0]["reason"])

    def test_oa_pdf_ingestion_does_not_generate_paper_request(self) -> None:
        reference = ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "Open access NF-kB macrophage paper",
                "doi": "10.1234/oa.2021.001",
                "year": "2021",
                "abstract": "NF-kB macrophage biology.",
                "full_text": "Full text about NF-kB macrophage biology and inflammatory cytokines.",
                "search_task_id": self.task["id"],
                "access_status": "oa_pdf_downloaded",
                "relevance_score": 0.9,
            },
        )
        ros.build_project_research_kb(
            self.agent_root,
            {"project_id": self.project["id"], "reference_ids": [reference["id"]], "include_article_analysis": False},
        )

        result = ros.generate_paper_requests_for_task(
            self.agent_root,
            {"project_id": self.project["id"], "task_id": self.task["id"]},
        )

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(ros.list_paper_requests(self.agent_root, project_id=self.project["id"]), [])


if __name__ == "__main__":
    unittest.main()
