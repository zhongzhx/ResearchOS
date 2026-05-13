import unittest

from backend.researchos.tasks.task_memory_commit import build_memory_commit_record


class TaskMemoryCommitTests(unittest.TestCase):
    def test_memory_commit_record_classifies_promoted_pages(self) -> None:
        record = build_memory_commit_record(
            {"rejected_items": [{"target": "claims", "reason": "missing evidence"}], "required_human_review": True},
            {
                "pages": [
                    {"page_type": "claim", "path": "claim.md"},
                    {"page_type": "dataset", "path": "dataset.md"},
                    {"page_type": "decision", "path": "decision.md"},
                    {"page_type": "failure", "path": "failure.md"},
                ],
                "rejected_items": [],
            },
            graph_update={"edge_count": 1},
            context_index_update={"project_id": "project_1"},
            pending_skill={"created": True},
        )

        self.assertEqual(len(record["promoted_claims"]), 1)
        self.assertEqual(len(record["promoted_datasets"]), 1)
        self.assertEqual(len(record["promoted_decisions"]), 1)
        self.assertEqual(len(record["failure_memory"]), 1)
        self.assertTrue(record["pending_skill"]["created"])
        self.assertTrue(record["required_human_review"])
        self.assertTrue(record["rejected_items"])


if __name__ == "__main__":
    unittest.main()
