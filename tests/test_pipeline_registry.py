import json
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.researchos.skills.pipeline_registry import (
    get_pipeline_for_intent,
    list_pipelines,
    route_query_to_pipeline,
    validate_pipeline_registry_consistency,
    validate_pipeline_permissions,
)


ROOT = Path(__file__).resolve().parents[1]


class PipelineRegistryTests(unittest.TestCase):
    def test_pipeline_registry_json_is_not_empty(self) -> None:
        data = json.loads((ROOT / "skills" / "researchos_skill_library" / "pipeline_registry.json").read_text(encoding="utf-8-sig"))

        self.assertGreater(len(data.get("pipelines", [])), 0)

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
        self.assertEqual(route_query_to_pipeline("帮我做项目周报")["pipeline_name"], "weekly_reporting")
        self.assertEqual(route_query_to_pipeline("从这段文字里提取实体")["pipeline_name"], "entity_extraction")

    def test_route_prefers_registry_over_direct_route_fallbacks(self) -> None:
        registry_pipeline = {
            "pipeline_name": "custom_registry_pipeline",
            "intent": "custom_registry_pipeline",
            "trigger_phrases": ["文献"],
        }

        with patch("backend.researchos.skills.pipeline_registry.list_pipelines", return_value=[registry_pipeline]):
            self.assertEqual(route_query_to_pipeline("文献 route should prefer registry")["pipeline_name"], "custom_registry_pipeline")

    def test_browser_pipeline_requires_authorization(self) -> None:
        pipeline = get_pipeline_for_intent("browser_research_learning")
        permissions = validate_pipeline_permissions(pipeline)

        self.assertTrue(pipeline["requires_user_authorization"])
        self.assertFalse(permissions["auto_executable_without_user_authorization"])

    def test_registry_consistency_check_accepts_current_registry(self) -> None:
        report = validate_pipeline_registry_consistency()

        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
