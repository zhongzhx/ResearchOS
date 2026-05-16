import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.execution.runtime_adapter import import_research_os_mvp


ros = import_research_os_mvp()
import research_memory_canonical as canonical_memory  # noqa: E402


class ResearchOSProjectPurgeCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_project_purge_cleanup_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"title": "Purge Cleanup Demo", "research_area": "NF-kB"})
        self.project_id = self.project["id"]
        self.harvest_dir = self.agent_root / "research_os_files" / "literature_harvest" / self.project_id
        self.harvest_dir.mkdir(parents=True)
        (self.harvest_dir / "orphan_pdf_work_file.pdf").write_text("pdf payload", encoding="utf-8")
        ros.upsert_experiment(
            self.agent_root,
            {
                "project_id": self.project_id,
                "title": "LPS stimulation",
                "experiment_type": "cell assay",
                "result_summary": "NF-kB changed.",
                "status": "completed",
            },
        )
        ros.upsert_sample(
            self.agent_root,
            {
                "project_id": self.project_id,
                "sample_code": "RAW264.7-LPS",
                "sample_type": "cell",
                "current_status": "used",
            },
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_purge_removes_project_runtime_dirs_and_experiment_memory(self) -> None:
        self.assertTrue(self.harvest_dir.exists())
        self.assertTrue(canonical_memory.list_experiments(self.agent_root, self.project_id))
        self.assertTrue(canonical_memory.list_samples(self.agent_root, self.project_id))

        plan = ros.purge_project(self.agent_root, self.project_id, dry_run=True)["deletion_plan"]
        result = ros.purge_project(self.agent_root, self.project_id, confirmation=plan["confirmation_phrase"])

        self.assertTrue(result["executed"])
        self.assertFalse(Path(self.project["root_dir"]).exists())
        self.assertFalse(self.harvest_dir.exists())
        self.assertEqual(canonical_memory.list_experiments(self.agent_root, self.project_id), [])
        self.assertEqual(canonical_memory.list_samples(self.agent_root, self.project_id), [])


if __name__ == "__main__":
    unittest.main()
