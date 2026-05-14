import unittest

from backend.researchos.product.feature_flows import run_product_feature


class DataAnalysisWorkflowProductTests(unittest.TestCase):
    def test_data_analysis_demo_csv_returns_summary_without_statistics_claims(self) -> None:
        result = run_product_feature(
            "data_analysis_workflow",
            {
                "project_id": "demo_project",
                "mode": "demo",
                "inline_csv": "group,response\ncontrol,1.0\nstim,1.8\nstim,2.0\n",
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["selected_pipeline"], "data_analysis_to_narrative")
        self.assertTrue(any(artifact["type"] == "data_summary" for artifact in result["artifacts"]))
        self.assertTrue(any("statistics" in warning.lower() for warning in result["warnings"]))
        self.assertNotIn("p < 0.05", result["summary"].lower())


if __name__ == "__main__":
    unittest.main()
