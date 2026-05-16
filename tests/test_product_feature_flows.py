import unittest

from backend.researchos.product.feature_flows import (
    CORE_FEATURE_IDS,
    get_product_feature,
    list_product_features,
    run_product_feature_demo,
)


class ProductFeatureFlowsTests(unittest.TestCase):
    def test_core_feature_contracts_are_registered(self) -> None:
        features = list_product_features()
        ids = {feature["feature_id"] for feature in features}

        self.assertEqual(ids, set(CORE_FEATURE_IDS))
        self.assertEqual(len(features), 8)
        for feature in features:
            with self.subTest(feature=feature["feature_id"]):
                self.assertIn(feature["status"], {"ready", "partial", "disabled", "not_connected"})
                self.assertTrue(feature["display_name"])
                self.assertTrue(feature["preferred_pipeline"])
                self.assertIsInstance(feature["required_backend_api"], list)
                self.assertIsInstance(feature["required_skills"], list)
                self.assertIsInstance(feature["expected_artifacts"], list)
                self.assertIsInstance(feature["expected_frontend_panels"], list)
                self.assertIsInstance(feature["safety_requirements"], list)

    def test_demo_flow_returns_product_lifecycle(self) -> None:
        feature = get_product_feature("experiment_design_workflow")
        result = run_product_feature_demo("experiment_design_workflow", project_id="demo_project")

        self.assertEqual(feature["preferred_pipeline"], "experiment_design")
        self.assertTrue(result["ok"])
        self.assertEqual(result["feature_id"], "experiment_design_workflow")
        self.assertEqual(result["selected_pipeline"], "experiment_design")
        self.assertIn("Goal", result["task_lifecycle"])
        self.assertIn("Validation", result["task_lifecycle"])
        self.assertTrue(result["artifacts"])
        self.assertTrue(result["memory_updates"])


if __name__ == "__main__":
    unittest.main()
