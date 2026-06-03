import unittest

from backend.researchos.skills.pipeline_registry import get_pipeline_for_intent, route_query_to_pipeline


class NatureWorkflowRegistryTests(unittest.TestCase):
    def test_required_workflows_are_machine_readable(self) -> None:
        intents = [
            "literature_harvest_and_kb",
            "paper_deep_reading",
            "citation_support",
            "nature_figure_generation",
            "nature_paper_to_ppt",
            "nature_academic_polishing",
            "nature_reviewer_response",
            "nature_data_availability",
            "experiment_design",
            "protocol_to_sop",
            "failure_recovery",
            "weekly_report",
            "scientific_data_analysis",
        ]
        for intent in intents:
            with self.subTest(intent=intent):
                pipeline = get_pipeline_for_intent(intent)
                for field in [
                    "intent",
                    "user_title",
                    "required_inputs",
                    "optional_inputs",
                    "execution_skills",
                    "allowed_tools",
                    "expected_artifacts",
                    "project_scope_required",
                    "current_status",
                    "honest_limitations",
                    "requires_user_authorization",
                    "validation_rules",
                ]:
                    self.assertIn(field, pipeline)
                self.assertTrue(pipeline["project_scope_required"])

    def test_chat_phrases_route_through_json_registry(self) -> None:
        self.assertEqual(route_query_to_pipeline("帮我把这篇论文做成组会 PPT")["intent"], "nature_paper_to_ppt")
        self.assertEqual(route_query_to_pipeline("用这张表做科研绘图")["intent"], "nature_figure_generation")
        self.assertEqual(route_query_to_pipeline("帮我润色摘要")["intent"], "nature_academic_polishing")


if __name__ == "__main__":
    unittest.main()
