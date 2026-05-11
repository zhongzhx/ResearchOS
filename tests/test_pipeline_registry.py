import unittest

from backend.researchos.skills.pipeline_registry import (
    get_pipeline_for_intent,
    list_pipelines,
    route_query_to_pipeline,
    validate_pipeline_permissions,
)


class PipelineRegistryTests(unittest.TestCase):
    def test_registry_contains_required_product_pipelines(self) -> None:
        names = {item["pipeline_name"] for item in list_pipelines()}

        self.assertTrue(
            {
                "literature_harvest",
                "browser_research_learning",
                "research_route_planning",
                "protocol_to_sop",
                "experiment_design",
                "data_analysis_to_narrative",
                "failure_recovery",
                "writing_review",
                "weekly_reporting",
                "entity_extraction",
            }.issubset(names)
        )

    def test_query_routes_to_expected_pipelines(self) -> None:
        self.assertEqual(route_query_to_pipeline("帮我下载先天免疫文献")["pipeline_name"], "literature_harvest")
        self.assertEqual(route_query_to_pipeline("浏览器学习这个网页")["pipeline_name"], "browser_research_learning")
        self.assertEqual(route_query_to_pipeline("把 Methods 转 SOP")["pipeline_name"], "protocol_to_sop")
        self.assertEqual(route_query_to_pipeline("分析 CSV 并写结果段")["pipeline_name"], "data_analysis_to_narrative")
        self.assertEqual(route_query_to_pipeline("模拟审稿人批评")["pipeline_name"], "writing_review")
        self.assertEqual(route_query_to_pipeline("实验失败复盘")["pipeline_name"], "failure_recovery")

    def test_browser_pipeline_requires_authorization(self) -> None:
        pipeline = get_pipeline_for_intent("browser_research_learning")
        permissions = validate_pipeline_permissions(pipeline)

        self.assertTrue(pipeline["requires_user_authorization"])
        self.assertFalse(permissions["auto_executable_without_user_authorization"])


if __name__ == "__main__":
    unittest.main()
