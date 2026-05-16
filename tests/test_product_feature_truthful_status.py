import unittest

from backend.researchos.product.feature_flows import list_product_features, run_product_feature


class ProductFeatureTruthfulStatusTests(unittest.TestCase):
    def test_all_eight_features_have_truthful_non_ready_status_for_unconnected_dependencies(self) -> None:
        features = {row["feature_id"]: row for row in list_product_features()}

        self.assertEqual(len(features), 8)
        self.assertEqual(features["literature_harvest_workflow"]["status"], "partial")
        self.assertEqual(features["data_analysis_workflow"]["status"], "partial")
        self.assertEqual(features["dual_agent_research_task"]["status"], "partial")
        self.assertEqual(features["experiment_design_workflow"]["status"], "partial")
        self.assertIn("external_literature_search", features["literature_harvest_workflow"]["not_connected_dependencies"])
        self.assertIn("xlsx_parser", features["data_analysis_workflow"]["not_connected_dependencies"])

    def test_data_parser_without_inline_csv_returns_not_connected(self) -> None:
        result = run_product_feature("data_analysis_workflow", {"project_id": "p1"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "not_connected")
        self.assertIn("parser_not_connected", " ".join(result["warnings"]))


if __name__ == "__main__":
    unittest.main()
