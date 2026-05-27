import csv
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "researchos_skill_library" / "02_literature_browser_ingestion" / "keyword-research-harvest"
SCRIPT = SKILL_ROOT / "scripts" / "run_keyword_harvest_no_dedup.py"
CONTINUE_SCRIPT = SKILL_ROOT / "scripts" / "continue_download_and_dedup.py"
CONFIG_TEMPLATE = SKILL_ROOT / "references" / "config_template.json"


class KeywordHarvestLegacyEntrypointTests(unittest.TestCase):
    def test_legacy_entrypoint_loads_package_download_modules(self) -> None:
        with tempfile.TemporaryDirectory(prefix="keyword_harvest_entrypoint_") as tmp:
            output_root = Path(tmp) / "runs"
            run_root = output_root / "entrypoint-test"
            raw_dir = run_root / "raw_api_results"
            raw_dir.mkdir(parents=True)
            with (raw_dir / "openalex_records.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "title",
                        "abstract",
                        "source_database",
                        "source_record_id",
                        "open_access_flag",
                        "doi",
                        "pmid",
                        "pmcid",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "title": "Entrypoint import regression paper",
                        "abstract": "A local fixture used without any download URL.",
                        "source_database": "fixture",
                        "source_record_id": "fixture-1",
                        "open_access_flag": "false",
                        "doi": "",
                        "pmid": "",
                        "pmcid": "",
                    }
                )

            config = json.loads(CONFIG_TEMPLATE.read_text(encoding="utf-8"))
            config["include_terms"] = ["entrypoint"]
            config["secondary_terms"] = []
            config["delay_seconds"]["download"] = 0
            config_path = Path(tmp) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output-root",
                    str(output_root),
                    "--config",
                    str(config_path),
                    "--run-name",
                    run_root.name,
                    "--skip-search",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((run_root / "keyword_research_candidate_table.csv").is_file())
            self.assertTrue((run_root / "keyword_research_harvest_summary.md").is_file())

    def test_continue_entrypoint_loads_institutional_resolver_package(self) -> None:
        with tempfile.TemporaryDirectory(prefix="keyword_harvest_continue_") as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            dependency_root = Path(tmp) / "dependencies"
            dependency_root.mkdir()
            (dependency_root / "requests.py").write_text(
                "class Session:\n"
                "    def __init__(self):\n"
                "        self.headers = {}\n"
                "class RequestException(Exception):\n"
                "    pass\n"
                "class exceptions:\n"
                "    Timeout = RequestException\n"
                "    ConnectionError = RequestException\n"
                "    RequestException = RequestException\n",
                encoding="utf-8",
            )
            bs4_root = dependency_root / "bs4"
            bs4_root.mkdir()
            (bs4_root / "__init__.py").write_text("class BeautifulSoup:\n    pass\n", encoding="utf-8")
            with (run_root / "keyword_research_candidate_table.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["record_id", "exclusion_reason_if_any", "title", "doi"])
                writer.writeheader()

            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(
                part for part in [str(dependency_root), env.get("PYTHONPATH", "")] if part
            )
            result = subprocess.run(
                [sys.executable, str(CONTINUE_SCRIPT), "--run-root", str(run_root), "--institutional"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("literature_harvest package not found", result.stdout)

    def test_summary_counts_modern_pdf_download_status(self) -> None:
        spec = importlib.util.spec_from_file_location("legacy_keyword_harvest_entrypoint", SCRIPT)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="keyword_harvest_summary_") as tmp:
            run_root = Path(tmp)
            module.write_summary(
                run_root,
                pd.DataFrame([{"download_status": "oa_pdf_downloaded"}]),
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame([{"download_status": "oa_pdf_downloaded", "content_format": "pdf"}]),
            )

            summary = (run_root / "keyword_research_harvest_summary.md").read_text(encoding="utf-8")

            self.assertIn("- Successful downloads/full texts: `1`", summary)
            self.assertIn("- True PDFs: `1`", summary)

    def test_continue_retry_does_not_redownload_modern_pdf_success(self) -> None:
        with tempfile.TemporaryDirectory(prefix="keyword_harvest_retry_") as tmp:
            run_root = Path(tmp) / "run"
            log_dir = run_root / "download_logs"
            log_dir.mkdir(parents=True)
            with (run_root / "keyword_research_candidate_table.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["record_id", "exclusion_reason_if_any", "title", "doi"])
                writer.writeheader()
                writer.writerow({"record_id": "paper-1", "exclusion_reason_if_any": "", "title": "Downloaded paper", "doi": ""})
            with (log_dir / "keyword_research_download_log.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["record_id", "download_status", "content_format"])
                writer.writeheader()
                writer.writerow({"record_id": "paper-1", "download_status": "oa_pdf_downloaded", "content_format": "pdf"})

            result = subprocess.run(
                [sys.executable, str(CONTINUE_SCRIPT), "--run-root", str(run_root), "--retry-failed"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rows = list(csv.DictReader((log_dir / "keyword_research_download_log.csv").open("r", encoding="utf-8-sig")))
            self.assertEqual(rows[0]["download_status"], "oa_pdf_downloaded")


if __name__ == "__main__":
    unittest.main()
