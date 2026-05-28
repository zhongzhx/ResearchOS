import csv
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


class KeywordHarvestModernDownloadStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="keyword_harvest_status_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"title": "Status contract project"})
        self.run_root = self.tmp / "run"
        (self.run_root / "download_logs").mkdir(parents=True)
        (self.run_root / "downloaded_pdfs").mkdir()
        self.pdf_path = self.run_root / "downloaded_pdfs" / "paper-1.pdf"
        self.pdf_path.write_bytes(b"%PDF-1.4\nfixture\n")
        self.task = ros.create_literature_search_task(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "query": "status contract",
                "keywords": ["status contract"],
                "provider": "all",
                "status": "running",
                "references": [],
                "notes": ros.json_dumps({"run_root": str(self.run_root), "phase": "running"}),
            },
        )["task"]
        with (self.run_root / "keyword_research_candidate_table.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["record_id", "title", "doi", "authors", "year", "journal", "source_database", "abstract_if_available"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "record_id": "paper-1",
                    "title": "Modern status paper",
                    "doi": "10.1234/modern-status",
                    "authors": "Author",
                    "year": "2026",
                    "journal": "Fixture Journal",
                    "source_database": "fixture",
                    "abstract_if_available": "A fixture abstract.",
                }
            )
        with (self.run_root / "download_logs" / "keyword_research_download_log.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["record_id", "title", "doi", "final_pdf_path", "final_pdf_url", "download_status", "content_format"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "record_id": "paper-1",
                    "title": "Modern status paper",
                    "doi": "10.1234/modern-status",
                    "final_pdf_path": str(self.pdf_path),
                    "final_pdf_url": "https://example.org/paper.pdf",
                    "download_status": "oa_pdf_downloaded",
                    "content_format": "pdf",
                }
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_progress_counts_modern_pdf_download_status(self) -> None:
        progress = ros.collect_keyword_harvest_progress(self.agent_root, self.task["id"])["progress"]

        self.assertEqual(progress["pdf_count"], 1)
        self.assertEqual(progress["downloaded_count"], 1)

    def test_import_outputs_accepts_modern_pdf_download_status(self) -> None:
        result = ros.import_keyword_harvest_outputs(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "task_id": self.task["id"],
                "run_root": str(self.run_root),
                "skill_run_id": "skill-run-1",
            },
        )

        self.assertEqual(len(result["references"]), 1)
        self.assertEqual(result["references"][0]["full_text_path"], str(self.pdf_path))

    def test_incremental_ingest_accepts_modern_pdf_download_status(self) -> None:
        with patch.object(ros, "ingest_literature_pdf_record", return_value={}) as ingest:
            ros.incremental_ingest_literature_downloads(
                self.agent_root,
                project_id=self.project["id"],
                task_id=self.task["id"],
                skill_run_id="skill-run-1",
                provider="all",
                query="status contract",
                run_root=self.run_root,
            )

        ingest.assert_called_once()


if __name__ == "__main__":
    unittest.main()
