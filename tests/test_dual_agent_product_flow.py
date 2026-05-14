import unittest

from backend.researchos.product.feature_flows import run_product_feature


class DualAgentProductFlowTests(unittest.TestCase):
    def test_dual_agent_product_demo_returns_pipeline_skillrun_memory_and_handoff(self) -> None:
        result = run_product_feature(
            "dual_agent_research_task",
            {"project_id": "demo_project", "user_query": "帮我根据 RAW264.7 设计一个免疫激活实验", "mode": "demo"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["selected_pipeline"], "experiment_design")
        self.assertTrue(result["skillrun_id"])
        self.assertTrue(result["required_skills"])
        self.assertTrue(result["validation_report"])
        self.assertTrue(result["memory_update"])
        self.assertTrue(result["handoff"])


if __name__ == "__main__":
    unittest.main()
