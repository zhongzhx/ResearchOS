"""Tests for CLI candidate selection helpers."""

from __future__ import annotations

from literature_harvest.cli import _candidate_download_urls, _sort_records_for_download
from literature_harvest.models import DownloadResult, HarvestSummary


def test_download_selection_prefers_pdf_candidates_before_metadata_only():
    records = [
        {"title": "metadata", "landing_page_url": "https://pubmed.ncbi.nlm.nih.gov/1/"},
        {"title": "publisher pdf", "pdf_url": "https://example.org/article.pdf"},
        {"title": "pmc pdf", "pdf_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1/pdf/"},
    ]

    sorted_records = _sort_records_for_download(records)

    assert [row["title"] for row in sorted_records] == ["pmc pdf", "publisher pdf", "metadata"]


def test_manual_download_required_counts_in_summary():
    summary = HarvestSummary.from_results(
        "query",
        [DownloadResult(record_id="1", download_status="manual_download_required")],
    )

    assert summary.manual_download_required == 1
    assert summary.failed == 0


def test_candidate_urls_include_official_plos_pdf_from_doi():
    urls = _candidate_download_urls(
        {
            "doi": "10.1371/journal.pone.0000001",
            "landing_page_url": "https://example.org/landing",
        }
    )

    assert urls[0] == "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0000001&type=printable"
