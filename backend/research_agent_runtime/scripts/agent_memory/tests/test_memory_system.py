from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_memory.api import (
    archive_memory,
    build_memory_context,
    consolidate_memory,
    create_experiment,
    create_group,
    create_memory,
    create_project,
    create_protocol,
    create_sample,
    extract_and_queue_if_needed,
    extract_memory_candidates,
    get_current_project_view,
    link_file_to_experiment,
    list_project_memory,
    register_data_file,
    retrieve_memory,
)
from agent_memory.protocols import latest_protocol


class AgentMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.group = create_group(self.root, {"name": "Demo lab"})
        self.project = create_project(
            self.root,
            {
                "group_id": self.group["id"],
                "title": "Macrophage anti-inflammatory assay",
                "research_question": "Does compound 3 reduce inflammatory markers in RAW264.7 cells?",
                "hypothesis": "Compound 3 reduces LPS-induced inflammatory response.",
                "stage": "pilot",
                "target_output": "manuscript",
            },
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_create_project_memory(self) -> None:
        memories = list_project_memory(self.root, self.project["id"])
        self.assertTrue(any(item["memory_type"] == "project_memory" for item in memories))

    def test_create_experiment_memory_from_note(self) -> None:
        note = "Experiment 1: RAW264.7 cells treated with compound 3 at 10 uM for 24 h. LPS control included. Result decreased TNF-alpha."
        candidate = extract_memory_candidates(note, {"project_id": self.project["id"]})
        self.assertTrue(candidate["should_write"])
        exp = create_experiment(
            self.root,
            {
                "project_id": self.project["id"],
                "title": candidate["experiment"]["title"],
                "experiment_type": candidate["experiment"]["experiment_type"],
                "groups": candidate["experiment"]["groups"],
                "sample_ids": [sample["sample_code"] for sample in candidate["samples"]],
                "result_summary": "TNF-alpha decreased in treated group.",
                "conclusion": "Preliminary anti-inflammatory effect.",
            },
        )
        self.assertEqual(exp["project_id"], self.project["id"])

    def test_register_file_and_link_to_experiment(self) -> None:
        exp = create_experiment(self.root, {"project_id": self.project["id"], "title": "ELISA pilot"})
        data_file = register_data_file(self.root, {"project_id": self.project["id"], "filename": "elisa.csv", "columns": ["sample", "group", "TNF"]})
        linked = link_file_to_experiment(self.root, data_file["id"], exp["id"])
        self.assertEqual(linked["experiment_id"], exp["id"])

    def test_retrieve_completed_experiments_for_project(self) -> None:
        create_experiment(self.root, {"project_id": self.project["id"], "title": "qPCR completed", "status": "completed"})
        rows = retrieve_memory(self.root, {"project_id": self.project["id"], "query": "completed experiments", "memory_types": ["experiment_memory"], "max_results": 10})
        self.assertTrue(rows)

    def test_retrieve_sample_specific_memory(self) -> None:
        sample = create_sample(self.root, {"group_id": self.group["id"], "project_id": self.project["id"], "sample_code": "C3-B01", "sample_type": "compound", "batch": "B01"})
        rows = retrieve_memory(self.root, {"project_id": self.project["id"], "entities": ["C3-B01"], "max_results": 10})
        self.assertTrue(any(sample["sample_code"] in str(row.get("entities")) for row in rows))

    def test_supersede_old_project_decision(self) -> None:
        old = create_memory(self.root, {"project_id": self.project["id"], "memory_type": "decision_memory", "subject": "animal plan", "content": "Use animal experiments in next phase."})
        new = create_memory(
            self.root,
            {
                "project_id": self.project["id"],
                "memory_type": "decision_memory",
                "subject": "animal plan",
                "content": "Switch to cell-only validation before animal work.",
                "supersedes": [old["id"]],
            },
        )
        active = retrieve_memory(self.root, {"project_id": self.project["id"], "query": "animal plan", "memory_types": ["decision_memory"]})
        self.assertEqual(active[0]["id"], new["id"])

    def test_preserve_negative_results(self) -> None:
        create_experiment(self.root, {"project_id": self.project["id"], "title": "Failed qPCR", "status": "failed", "result_summary": "No amplification in two runs."})
        rows = retrieve_memory(self.root, {"project_id": self.project["id"], "query": "failed qPCR", "memory_types": ["failure_memory"]})
        self.assertTrue(rows)

    def test_build_memory_context_for_manuscript(self) -> None:
        create_memory(self.root, {"project_id": self.project["id"], "memory_type": "writing_memory", "subject": "style", "content": "Prefer concise journal style."})
        consolidate_memory(self.root, {"user_id": "local_user", "project_id": self.project["id"]})
        context = build_memory_context(self.root, {"user_id": "local_user", "project_id": self.project["id"], "query": "write manuscript"})
        self.assertIn("Relevant Research Memory", context)
        self.assertIn("User or group preferences", context)

    def test_consolidate_ledger_into_project_view(self) -> None:
        result = consolidate_memory(self.root, {"user_id": "local_user", "project_id": self.project["id"]})
        self.assertEqual(result["project_count"], 1)
        self.assertIsNotNone(get_current_project_view(self.root, self.project["id"]))

    def test_incomplete_experiment_is_kept(self) -> None:
        exp = create_experiment(self.root, {"project_id": self.project["id"], "title": "Incomplete note"})
        self.assertEqual(exp["title"], "Incomplete note")
        self.assertIn("sample_ids", exp)

    def test_prevent_duplicate_memory_records(self) -> None:
        payload = {"project_id": self.project["id"], "memory_type": "task_memory", "subject": "next", "content": "Repeat ELISA with n=3."}
        first = create_memory(self.root, payload)
        second = create_memory(self.root, payload)
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second.get("duplicate_ignored"))

    def test_archive_without_deleting_evidence(self) -> None:
        memory = create_memory(self.root, {"project_id": self.project["id"], "memory_type": "task_memory", "subject": "old task", "content": "Old task"})
        archived = archive_memory(self.root, memory["id"])
        self.assertEqual(archived["status"], "archived")
        active = retrieve_memory(self.root, {"project_id": self.project["id"], "query": "Old task"})
        self.assertFalse(any(row["id"] == memory["id"] for row in active))

    def test_latest_active_protocol_version(self) -> None:
        create_protocol(self.root, {"group_id": self.group["id"], "name": "LC-MS preprocessing", "version": "v1"})
        protocol = create_protocol(self.root, {"group_id": self.group["id"], "name": "LC-MS preprocessing", "version": "v2"})
        latest = latest_protocol(self.root, "LC-MS preprocessing", self.group["id"])
        self.assertEqual(latest["id"], protocol["id"])

    def test_search_by_cell_line_compound_assay_instrument(self) -> None:
        create_memory(
            self.root,
            {
                "project_id": self.project["id"],
                "memory_type": "experiment_memory",
                "subject": "RAW264.7 LC-MS assay",
                "content": "RAW264.7 cells treated with compound 3; LC-MS instrument used.",
                "entities": {"cell_line": "RAW264.7", "compound": "compound 3", "instrument": "LC-MS"},
                "tags": ["RAW264.7", "compound 3", "LC-MS"],
            },
        )
        rows = retrieve_memory(self.root, {"project_id": self.project["id"], "query": "RAW264.7 compound 3 LC-MS"})
        self.assertTrue(rows)

    def test_low_confidence_extraction_review_queue(self) -> None:
        result = extract_and_queue_if_needed(self.root, {"text": "Maybe remember this unclear note.", "group_id": self.group["id"]})
        self.assertIsNotNone(result["review_item"])


if __name__ == "__main__":
    unittest.main()
