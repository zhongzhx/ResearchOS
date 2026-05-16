import unittest

from backend.researchos.product.feature_flows import run_product_feature_demo


class ExecutionVisibilityTests(unittest.TestCase):
    def test_demo_result_exposes_run_details_for_client(self) -> None:
        result = run_product_feature_demo("dual_agent_research_task", project_id="demo_project")

        self.assertTrue(result["ok"])
        self.assertIn("execution_status", result)
        self.assertIn("artifacts", result)
        self.assertIn("validation_report", result)
        self.assertIn("memory_update", result)
        self.assertIn("pending_skill", result)
        self.assertIn("raw_details", result)


if __name__ == "__main__":
    unittest.main()
