import unittest

from backend.researchos.skills.resolver_checker import run_resolver_smoke_tests


class ResolverCheckerPipelineTests(unittest.TestCase):
    def test_resolver_health_checks_catalog_legacy_and_pipeline_rules(self) -> None:
        report = run_resolver_smoke_tests()

        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["pipeline_entries"], 10)
        self.assertEqual(report["missing_canonical_paths"], [])
        self.assertEqual(report["legacy_map_errors"], [])
        self.assertEqual(report["pipelines_missing_validation_rules"], [])
        self.assertEqual(report["pipelines_missing_promotion_targets"], [])
        self.assertTrue(report["browser_pipeline_requires_authorization"])


if __name__ == "__main__":
    unittest.main()
