import unittest

from backend.researchos.product.feature_flows import run_product_feature


class LiteratureWorkflowProductTests(unittest.TestCase):
    def test_literature_workflow_dry_run_returns_task_or_partial_state(self) -> None:
        result = run_product_feature(
            "literature_harvest_workflow",
            {"project_id": "demo_project", "keywords": ["RAW264.7", "innate immunity"], "mode": "dry_run"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["feature_id"], "literature_harvest_workflow")
        self.assertIn(result["status"], {"ready", "partial", "not_connected"})
        self.assertEqual(result["selected_pipeline"], "literature_harvest")
        self.assertIn("Library / Evidence", result["task_lifecycle"]["Artifacts"])
        self.assertTrue(any(action["intent"] == "review_paper_requests" for action in result["next_actions"]))


if __name__ == "__main__":
    unittest.main()
